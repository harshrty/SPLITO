"""Anomaly detectors — one isolated function per anomaly type.

Each detector: (rows, ctx) -> list[AnomalyDraft]. `rows` are StagedRow instances.
ImportService loops the DETECTORS registry over the staged rows. Detectors never
mutate anything — they only surface problems. Resolution happens at commit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .context import (GroupContext, normalize_name, parse_amount,
                      parse_detail_map, parse_name_list)


@dataclass
class AnomalyDraft:
    staged_row_id: int
    anomaly_type: str
    severity: str          # 'block' | 'warn'
    detail: str
    proposed_action: str


def _amount(raw):
    return parse_amount(raw.get("amount", ""))


def _date(raw) -> date | None:
    try:
        return date.fromisoformat((raw.get("date", "") or "").strip()[:10])
    except ValueError:
        return None


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


# ---- row-local detectors -------------------------------------------------

def missing_payer(rows, ctx):
    return [AnomalyDraft(r.id, "missing_payer", "block",
                         "paid_by is empty — who paid?", "request_input")
            for r in rows if not r.raw_json.get("paid_by", "").strip()]


def missing_currency(rows, ctx):
    return [AnomalyDraft(r.id, "missing_currency", "warn",
                         "currency is blank — defaulting to INR", "convert_currency")
            for r in rows if not r.raw_json.get("currency", "").strip()]


def negative_amount(rows, ctx):
    out = []
    for r in rows:
        amt = _amount(r.raw_json)
        if amt is not None and amt < 0:
            out.append(AnomalyDraft(r.id, "negative_amount", "block",
                                    f"amount {amt} is negative — refund or error?", "request_input"))
    return out


def zero_amount(rows, ctx):
    out = []
    for r in rows:
        amt = _amount(r.raw_json)
        if amt is not None and amt == 0:
            out.append(AnomalyDraft(r.id, "zero_amount", "warn",
                                    "amount is 0 — no economic effect, will skip", "skip"))
    return out


def sub_unit_amount(rows, ctx):
    out = []
    for r in rows:
        amt = _amount(r.raw_json)
        if amt is not None and amt.as_tuple().exponent < -2:
            out.append(AnomalyDraft(r.id, "sub_unit_amount", "warn",
                                    f"amount {amt} has sub-paisa precision — will round HALF_UP", "convert_currency"))
    return out


def pct_not_100(rows, ctx):
    out = []
    for r in rows:
        if r.raw_json.get("split_type", "").strip() != "percentage":
            continue
        vals = parse_detail_map(r.raw_json.get("split_details", ""))
        total = 0
        ok = True
        for v in vals.values():
            a = parse_amount(v.replace("%", ""))
            if a is None:
                ok = False
                break
            total += a
        if ok and total != 100:
            out.append(AnomalyDraft(r.id, "pct_not_100", "block",
                                    f"percentages total {total}, not 100", "reject"))
    return out


def unequal_sum_mismatch(rows, ctx):
    out = []
    for r in rows:
        if r.raw_json.get("split_type", "").strip() != "unequal":
            continue
        amt = _amount(r.raw_json)
        vals = parse_detail_map(r.raw_json.get("split_details", ""))
        parsed = [parse_amount(v) for v in vals.values()]
        if amt is not None and all(p is not None for p in parsed) and sum(parsed) != amt:
            out.append(AnomalyDraft(r.id, "unequal_sum_mismatch", "block",
                                    f"unequal shares sum to {sum(parsed)}, expected {amt}", "reject"))
    return out


def type_detail_conflict(rows, ctx):
    out = []
    for r in rows:
        if (r.raw_json.get("split_type", "").strip() == "equal"
                and r.raw_json.get("split_details", "").strip()):
            out.append(AnomalyDraft(r.id, "type_detail_conflict", "warn",
                                    "split_type=equal but split_details present — honoring equal", "skip"))
    return out


def out_of_bounds_date(rows, ctx):
    out = []
    for r in rows:
        d = _date(r.raw_json)
        if d is None:
            continue
        if (ctx.min_date and d < ctx.min_date) or (ctx.max_date and d > ctx.max_date):
            out.append(AnomalyDraft(r.id, "out_of_bounds_date", "block",
                                    f"date {d} is outside the group's lifetime", "reject"))
    return out


def ambiguous_date(rows, ctx):
    out = []
    for r in rows:
        note = (r.raw_json.get("notes", "") or "").lower()
        if "format is a mess" in note or ("april" in note and "may" in note):
            out.append(AnomalyDraft(r.id, "ambiguous_date", "block",
                                    "date is ambiguous (note flags it) — user must disambiguate", "request_input"))
    return out


# ---- context-aware (name / membership) detectors -------------------------

def _participant_tokens(raw):
    return parse_name_list(raw.get("split_with", ""))


def name_alias(rows, ctx):
    out = []
    for r in rows:
        names = _participant_tokens(r.raw_json)
        payer = r.raw_json.get("paid_by", "")
        if payer.strip():
            names = names + [payer]
        for tok in names:
            pid = ctx.resolve(tok)
            if pid is not None and tok.strip() != ctx.id_to_name.get(pid, ""):
                out.append(AnomalyDraft(r.id, "name_alias", "warn",
                                        f"'{tok}' resolved to '{ctx.id_to_name[pid]}'", "normalize_name"))
                break  # one alias note per row is enough
    return out


def non_member(rows, ctx):
    out = []
    for r in rows:
        for tok in _participant_tokens(r.raw_json):
            if ctx.resolve(tok) is None:
                out.append(AnomalyDraft(r.id, "non_member", "warn",
                                        f"'{tok}' is not a known member — add as guest?", "request_input"))
    return out


def ex_member(rows, ctx):
    out = []
    for r in rows:
        d = _date(r.raw_json)
        if d is None:
            continue
        for tok in _participant_tokens(r.raw_json):
            pid = ctx.resolve(tok)
            if pid is None or pid in ctx.guest_ids:
                continue
            if not ctx.is_member_on(pid, d):
                out.append(AnomalyDraft(r.id, "ex_member", "block",
                                        f"'{ctx.id_to_name[pid]}' was not a member on {d}", "exclude_person"))
    return out


def settlement_as_expense(rows, ctx):
    keywords = ("paid", "back", "settle", "deposit", "repay")
    out = []
    for r in rows:
        parts = _participant_tokens(r.raw_json)
        payer = r.raw_json.get("paid_by", "").strip()
        stype = r.raw_json.get("split_type", "").strip()
        text = (r.raw_json.get("description", "") + " " + r.raw_json.get("notes", "")).lower()
        if len(parts) == 1 and payer and normalize_name(parts[0]) != normalize_name(payer):
            if stype == "" or any(k in text for k in keywords):
                out.append(AnomalyDraft(r.id, "settlement_as_expense", "block",
                                        "looks like a payment, not a shared expense", "reclassify_settlement"))
    return out


# ---- cross-row duplicate detectors ---------------------------------------

def _dup_pairs(rows):
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            yield rows[i], rows[j]


def exact_dup(rows, ctx):
    out = []
    for a, b in _dup_pairs(rows):
        ra, rb = a.raw_json, b.raw_json
        if _date(ra) != _date(rb) or _date(ra) is None:
            continue
        ta, tb = _tokens(ra.get("description", "")), _tokens(rb.get("description", ""))
        if not ta or not tb:
            continue
        jac = len(ta & tb) / len(ta | tb)
        same_payer = normalize_name(ra.get("paid_by", "")) == normalize_name(rb.get("paid_by", ""))
        same_amount = _amount(ra) == _amount(rb)
        if jac >= 0.6 and same_payer and same_amount:
            out.append(AnomalyDraft(b.id, "exact_dup", "block",
                                    f"duplicate of row {a.row_number} (same date/payer/amount)", "void_dup"))
    return out


def fuzzy_dup(rows, ctx):
    out = []
    for a, b in _dup_pairs(rows):
        ra, rb = a.raw_json, b.raw_json
        if _date(ra) != _date(rb) or _date(ra) is None:
            continue
        ta, tb = _tokens(ra.get("description", "")), _tokens(rb.get("description", ""))
        if not ta or not tb:
            continue
        jac = len(ta & tb) / len(ta | tb)
        same_payer = normalize_name(ra.get("paid_by", "")) == normalize_name(rb.get("paid_by", ""))
        same_amount = _amount(ra) == _amount(rb)
        if jac >= 0.6 and not (same_payer and same_amount):
            out.append(AnomalyDraft(b.id, "fuzzy_dup", "block",
                                    f"likely same expense as row {a.row_number}, different amount/payer — pick one",
                                    "merge"))
    return out


DETECTORS = [
    missing_payer, missing_currency, negative_amount, zero_amount, sub_unit_amount,
    pct_not_100, unequal_sum_mismatch, type_detail_conflict, out_of_bounds_date,
    ambiguous_date, name_alias, non_member, ex_member, settlement_as_expense,
    exact_dup, fuzzy_dup,
]


def run_all(rows, ctx: GroupContext) -> list[AnomalyDraft]:
    drafts = []
    for detector in DETECTORS:
        drafts.extend(detector(rows, ctx))
    return drafts
