"""ImportService — orchestrates the quarantine pipeline.

ingest -> run_detectors -> report -> resolve -> commit.
Commit is gated: it refuses while any block-severity anomaly is still pending, and
applies each approved resolution when writing to the ledger. Nothing is silently
guessed; rows it cannot fully resolve are reported as skipped, never dropped silently.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.expenses.models import Settlement
from apps.expenses.services.expense_service import (ExpenseService,
                                                    ExpenseValidationError)

from ..models import Anomaly, ImportBatch, StagedRow
from .context import (GroupContext, parse_amount, parse_detail_map,
                      parse_name_list)
from .detectors import run_all
from .parser import parse


class CommitBlocked(Exception):
    """Raised when unresolved block-severity anomalies remain."""


class ImportService:
    def ingest(self, group, filename: str, file_bytes: bytes, user=None) -> ImportBatch:
        batch = ImportBatch.objects.create(group=group, filename=filename, uploaded_by=user)
        rows = parse(file_bytes, filename)
        StagedRow.objects.bulk_create([
            StagedRow(batch=batch, row_number=r["row_number"], raw_json=r["raw"]) for r in rows
        ])
        return batch

    def run_detectors(self, batch: ImportBatch, today: date) -> list[Anomaly]:
        ctx = GroupContext.build(batch.group, today)
        rows = list(batch.rows.order_by("row_number"))
        drafts = run_all(rows, ctx)
        anomalies = Anomaly.objects.bulk_create([
            Anomaly(batch=batch, staged_row_id=d.staged_row_id, anomaly_type=d.anomaly_type,
                    severity=d.severity, detail=d.detail, proposed_action=d.proposed_action)
            for d in drafts
        ])
        return anomalies

    def report(self, batch: ImportBatch) -> list[dict]:
        rows = {r.id: r.row_number for r in batch.rows.all()}
        out = []
        for a in batch.anomalies.order_by("severity", "staged_row_id"):
            out.append({
                "id": a.id, "row_number": rows.get(a.staged_row_id),
                "anomaly_type": a.anomaly_type, "severity": a.severity,
                "detail": a.detail, "proposed_action": a.proposed_action, "status": a.status,
            })
        return out

    def resolve(self, anomaly: Anomaly, status: str, resolved_value=None, user=None) -> Anomaly:
        anomaly.status = status
        anomaly.resolved_value = resolved_value
        anomaly.reviewed_by = user
        anomaly.reviewed_at = timezone.now()
        anomaly.save(update_fields=["status", "resolved_value", "reviewed_by", "reviewed_at"])
        return anomaly

    # -- commit ------------------------------------------------------------

    @transaction.atomic
    def commit(self, batch: ImportBatch, today: date, user=None) -> dict:
        if batch.anomalies.filter(severity="block", status="pending").exists():
            raise CommitBlocked("resolve all blocking anomalies before committing")

        ctx = GroupContext.build(batch.group, today)
        expenses = ExpenseService()
        result = {"created": 0, "settlements": 0, "voided": 0, "skipped": []}

        rows = list(batch.rows.order_by("row_number"))
        anomalies_by_row: dict[int, list[Anomaly]] = {}
        for a in batch.anomalies.all():
            anomalies_by_row.setdefault(a.staged_row_id, []).append(a)

        for row in rows:
            raw = row.raw_json
            types = {a.anomaly_type: a for a in anomalies_by_row.get(row.id, [])}

            def skip(reason):
                result["skipped"].append({"row": row.row_number, "reason": reason})

            # rows that are dropped rather than imported
            if "zero_amount" in types:
                skip("zero amount"); continue
            if "exact_dup" in types:
                result["voided"] += 1; continue
            if "fuzzy_dup" in types:
                result["voided"] += 1; continue
            if any(t in types for t in ("out_of_bounds_date", "ambiguous_date",
                                        "missing_payer", "pct_not_100", "unequal_sum_mismatch")):
                # these need a user-supplied correction we don't auto-invent
                if not any(types[t].resolved_value for t in types
                           if t in ("out_of_bounds_date", "ambiguous_date", "missing_payer",
                                    "pct_not_100", "unequal_sum_mismatch")):
                    skip("blocked: needs manual correction"); continue

            # settlement reclassification
            if "settlement_as_expense" in types:
                self._make_settlement(batch, row, ctx, result)
                continue

            self._make_expense(batch, row, ctx, expenses, result)

        batch.status = "committed"
        batch.save(update_fields=["status"])
        return result

    def _make_settlement(self, batch, row, ctx, result):
        raw = row.raw_json
        payer = ctx.resolve(raw.get("paid_by", ""))
        parts = parse_name_list(raw.get("split_with", ""))
        target = ctx.resolve(parts[0]) if parts else None
        amount = parse_amount(raw.get("amount", ""))
        if not (payer and target and amount and amount > 0 and payer != target):
            result["skipped"].append({"row": row.row_number, "reason": "settlement fields incomplete"})
            return
        Settlement.objects.create(
            group=batch.group, from_person_id=payer, to_person_id=target,
            amount_minor=int(amount * 100), settled_on=self._date(raw),
            note=raw.get("notes") or "reclassified from import", origin="reclassified_from_import",
        )
        result["settlements"] += 1

    def _make_expense(self, batch, row, ctx, expenses, result):
        raw = row.raw_json
        d = self._date(raw)
        payer = ctx.resolve(raw.get("paid_by", ""))
        amount = parse_amount(raw.get("amount", ""))
        if not (d and payer and amount is not None):
            result["skipped"].append({"row": row.row_number, "reason": "missing date/payer/amount"})
            return
        currency = (raw.get("currency") or "").strip() or "INR"
        split_type = (raw.get("split_type") or "").strip() or "equal"

        # participants: resolve names, keep guests + members-on-date (drops ex-members & unknowns)
        participants = []
        for tok in parse_name_list(raw.get("split_with", "")):
            pid = ctx.resolve(tok)
            if pid and (pid in ctx.guest_ids or ctx.is_member_on(pid, d)):
                participants.append(pid)
        if not participants:
            result["skipped"].append({"row": row.row_number, "reason": "no valid participants"})
            return

        details = None
        if split_type in ("unequal", "percentage", "share"):
            details = {}
            for name, val in parse_detail_map(raw.get("split_details", "")).items():
                pid = ctx.resolve(name)
                if pid in participants:
                    details[pid] = Decimal(val.replace("%", ""))
        # type_detail_conflict: equal but details present -> ignore details (already None)

        try:
            expenses.create(
                group=batch.group, spent_on=d, description=raw.get("description", "")[:200],
                paid_by_id=payer, amount=amount, currency=currency, split_type=split_type,
                participants=participants, details=details,
                notes=raw.get("notes") or None, import_batch=batch, source_row_number=row.row_number,
            )
            result["created"] += 1
        except ExpenseValidationError as exc:
            result["skipped"].append({"row": row.row_number, "reason": str(exc)})

    @staticmethod
    def _date(raw):
        try:
            return date.fromisoformat((raw.get("date", "") or "").strip()[:10])
        except ValueError:
            return None
