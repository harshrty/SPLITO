"""Capstone end-to-end test: the full user journey over HTTP against the REAL xlsx.

Walks exactly what an end user does in the browser —
  create group -> scan sheet for people -> confirm roster -> upload & detect
  -> resolve anomalies -> commit -> read balances
— and asserts the money invariants (every expense reconciles, balances net to
zero) plus the audit fixes (idempotent commit, settlement reclassification).
"""
from datetime import date
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.expenses.models import Expense, FxRate

XLSX = Path(__file__).resolve().parents[3].parent / "EXPENSE FILE" / "expenses_export assigbment annex.xlsx"
TODAY = date(2026, 7, 9)


class EndToEndJourneyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="journey@flat.com", display_name="Journey", password="strongpass123")
        self.client.force_authenticate(self.user)
        FxRate.objects.create(currency="USD", rate_to_base="83.50", effective_date=date(2026, 1, 1))

    def _upload(self):
        return SimpleUploadedFile(XLSX.name, XLSX.read_bytes(),
                                  content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_full_import_journey_from_messy_sheet(self):
        # 1. create the group
        g = self.client.post("/api/groups/", {"name": "Flat 4B"}, format="json")
        self.assertEqual(g.status_code, 201, g.data)
        gid = g.data["id"]

        # 2. scan the sheet for people (nothing persisted yet)
        scan = self.client.post(f"/api/groups/{gid}/import/scan-roster/", {"file": self._upload()})
        self.assertEqual(scan.status_code, 200, scan.data)
        cands = scan.data["candidates"]
        # the messy variants collapsed: one 'Priya' carrying 'Priya S'
        priya = next(c for c in cands if c["canonical"] == "Priya")
        self.assertIn("Priya S", priya["variants"])

        # 3. confirm & create the roster (accept the scan's guest suggestions)
        people = [{"canonical": c["canonical"], "is_guest": c["suggested_guest"], "aliases": c["variants"]}
                  for c in cands]
        apply = self.client.post(f"/api/groups/{gid}/import/apply-roster/",
                                 {"start_date": scan.data["suggested_start_date"] or "2026-02-01", "people": people},
                                 format="json")
        self.assertEqual(apply.status_code, 201, apply.data)
        self.assertGreaterEqual(apply.data["people"], 5)
        self.assertGreaterEqual(apply.data["aliases"], 1)  # 'Priya S' linked

        # 4. upload & detect against the populated roster — the 158 non_member noise is gone
        up = self.client.post(f"/api/groups/{gid}/import/", {"file": self._upload()})
        self.assertEqual(up.status_code, 201, up.data)
        batch_id = up.data["batch_id"]
        report = up.data["report"]
        types = {a["anomaly_type"] for a in report}
        self.assertNotIn("non_member", types, "roster should have resolved every name")
        self.assertLess(len(report), 40, "report should be the real ~20, not 170+")
        # the meaningful catalog is present
        for t in ("exact_dup", "settlement_as_expense", "ex_member", "out_of_bounds_date"):
            self.assertIn(t, types, f"expected detector {t} to fire")

        # 5. commit is BLOCKED while block-severity anomalies are still pending
        blocked = self.client.post(f"/api/import/{batch_id}/commit/")
        self.assertEqual(blocked.status_code, 409, blocked.data)

        # 6. reviewer resolves every pending block (approve)
        for a in report:
            if a["severity"] == "block" and a["status"] == "pending":
                r = self.client.post(f"/api/import/anomalies/{a['id']}/resolve/", {"status": "approved"}, format="json")
                self.assertEqual(r.status_code, 200, r.data)

        # 7. commit → ledger written
        commit = self.client.post(f"/api/import/{batch_id}/commit/")
        self.assertEqual(commit.status_code, 200, commit.data)
        self.assertGreater(commit.data["created"], 5)
        self.assertGreaterEqual(commit.data["settlements"], 2)  # the two 'paid back' rows

        # 8. AUDIT FIX — a second commit is refused (idempotent), ledger not duplicated
        before = Expense.objects.filter(group_id=gid).count()
        again = self.client.post(f"/api/import/{batch_id}/commit/")
        self.assertEqual(again.status_code, 409, again.data)
        self.assertIn("already", again.data["detail"].lower())
        self.assertEqual(Expense.objects.filter(group_id=gid).count(), before)

        # 9. INVARIANT — every committed expense reconciles (shares sum to the amount)
        expenses = self.client.get(f"/api/groups/{gid}/expenses/").data
        active = [e for e in expenses if e["status"] == "active"]
        self.assertGreater(len(active), 5)
        for e in active:
            self.assertEqual(sum(s["computed_owed_minor"] for s in e["shares"]),
                             e["amount_base_minor"], f"expense {e['id']} does not reconcile")

        # 10. INVARIANT — balances net to exactly zero (no money created or lost)
        balances = self.client.get(f"/api/groups/{gid}/balances/").data
        self.assertEqual(sum(b["net_minor"] for b in balances), 0)

        # 11. simplified transfers tie out: debtors paid == creditors received
        simplified = self.client.get(f"/api/groups/{gid}/balances/simplified/").data
        owed = -sum(b["net_minor"] for b in balances if b["net_minor"] < 0)
        self.assertEqual(sum(t["amount_minor"] for t in simplified), owed)
