"""Regression tests for the audit fixes in the import commit pipeline.

Each test targets one previously-broken behaviour:
- commit idempotency (double-commit must not duplicate the ledger)
- reviewer corrections (resolved_value) are actually applied
- duplicate / settlement reclassification honour the reviewer's decision
- reclassified settlements convert currency instead of assuming INR 1:1
"""
from datetime import date
from io import StringIO

from django.test import TestCase

from apps.accounts.models import User
from apps.expenses.models import Expense, FxRate, Settlement
from apps.groups.models import ExpenseGroup, Membership, Person
from apps.imports.models import Anomaly
from apps.imports.services.import_service import (AlreadyCommitted,
                                                  ImportService)

TODAY = date(2026, 7, 9)
COLUMNS = ["date", "description", "paid_by", "amount", "currency",
           "split_type", "split_with", "split_details", "notes"]


def _csv(rows: list[dict]) -> bytes:
    buf = StringIO()
    buf.write(",".join(COLUMNS) + "\n")
    for r in rows:
        buf.write(",".join(str(r.get(c, "")) for c in COLUMNS) + "\n")
    return buf.getvalue().encode("utf-8")


class ImportFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="h@flat.com", display_name="H", password="strongpass123")
        self.group = ExpenseGroup.objects.create(name="Flat", created_by=self.user)
        self.aisha = Person.objects.create(group=self.group, canonical_name="Aisha")
        self.rohan = Person.objects.create(group=self.group, canonical_name="Rohan")
        for p in (self.aisha, self.rohan):
            Membership.objects.create(group=self.group, person=p, joined_on=date(2026, 2, 1))
        FxRate.objects.create(currency="USD", rate_to_base="83.50", effective_date=date(2026, 1, 1))
        self.svc = ImportService()

    def _batch(self, rows):
        batch = self.svc.ingest(self.group, "in.csv", _csv(rows), user=self.user)
        self.svc.run_detectors(batch, TODAY)
        return batch

    def _approve_all(self, batch):
        for a in batch.anomalies.filter(status="pending"):
            self.svc.resolve(a, "approved")

    # -- Fix 1: idempotent commit -----------------------------------------

    def test_double_commit_does_not_duplicate_ledger(self):
        batch = self._batch([{"date": "2026-03-01", "description": "Dinner", "paid_by": "Aisha",
                              "amount": "100", "currency": "INR", "split_type": "equal",
                              "split_with": "Aisha;Rohan"}])
        first = self.svc.commit(batch, TODAY)
        self.assertEqual(first["created"], 1)
        self.assertEqual(Expense.objects.filter(group=self.group).count(), 1)

        with self.assertRaises(AlreadyCommitted):
            self.svc.commit(batch, TODAY)
        # ledger unchanged after the blocked re-commit
        self.assertEqual(Expense.objects.filter(group=self.group).count(), 1)

    # -- Fix 2: reviewer corrections are applied --------------------------

    def test_missing_payer_resolution_is_applied(self):
        batch = self._batch([{"date": "2026-03-01", "description": "Groceries", "paid_by": "",
                              "amount": "200", "currency": "INR", "split_type": "equal",
                              "split_with": "Aisha;Rohan"}])
        mp = batch.anomalies.get(anomaly_type="missing_payer")
        # reviewer supplies the payer (by person id) — previously this was ignored
        self.svc.resolve(mp, "edited", resolved_value=self.aisha.id)
        self._approve_all(batch)
        result = self.svc.commit(batch, TODAY)

        self.assertEqual(result["created"], 1)
        exp = Expense.objects.get(group=self.group)
        self.assertEqual(exp.paid_by_id, self.aisha.id)

    def test_missing_payer_without_value_is_held_back(self):
        batch = self._batch([{"date": "2026-03-01", "description": "Groceries", "paid_by": "",
                              "amount": "200", "currency": "INR", "split_type": "equal",
                              "split_with": "Aisha;Rohan"}])
        self._approve_all(batch)  # approved but NO corrected value provided
        result = self.svc.commit(batch, TODAY)
        self.assertEqual(result["created"], 0)
        self.assertTrue(any("manual correction" in s["reason"] for s in result["skipped"]))

    # -- Fix 3: duplicate resolution is honoured --------------------------

    def test_rejected_duplicate_is_kept(self):
        rows = [
            {"date": "2026-03-02", "description": "Cab ride", "paid_by": "Aisha", "amount": "300",
             "currency": "INR", "split_type": "equal", "split_with": "Aisha;Rohan"},
            {"date": "2026-03-02", "description": "Cab ride", "paid_by": "Aisha", "amount": "300",
             "currency": "INR", "split_type": "equal", "split_with": "Aisha;Rohan"},
        ]
        batch = self._batch(rows)
        dup = batch.anomalies.get(anomaly_type="exact_dup")
        self.svc.resolve(dup, "rejected")  # "these are genuinely two rides — keep both"
        result = self.svc.commit(batch, TODAY)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["voided"], 0)

    def test_approved_duplicate_is_voided(self):
        rows = [
            {"date": "2026-03-02", "description": "Cab ride", "paid_by": "Aisha", "amount": "300",
             "currency": "INR", "split_type": "equal", "split_with": "Aisha;Rohan"},
            {"date": "2026-03-02", "description": "Cab ride", "paid_by": "Aisha", "amount": "300",
             "currency": "INR", "split_type": "equal", "split_with": "Aisha;Rohan"},
        ]
        batch = self._batch(rows)
        self._approve_all(batch)
        result = self.svc.commit(batch, TODAY)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["voided"], 1)

    # -- Fix 3b + 5: settlement reclassification + currency ---------------

    def test_rejected_settlement_reclass_imports_as_expense(self):
        batch = self._batch([{"date": "2026-03-03", "description": "settle up", "paid_by": "Rohan",
                              "amount": "500", "currency": "INR", "split_type": "",
                              "split_with": "Aisha"}])
        rc = batch.anomalies.get(anomaly_type="settlement_as_expense")
        self.svc.resolve(rc, "rejected")  # "no, it really was a shared expense"
        self._approve_all(batch)
        result = self.svc.commit(batch, TODAY)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["settlements"], 0)

    def test_reclassified_settlement_converts_currency(self):
        batch = self._batch([{"date": "2026-03-03", "description": "paid back", "paid_by": "Rohan",
                              "amount": "10", "currency": "USD", "split_type": "",
                              "split_with": "Aisha"}])
        self._approve_all(batch)
        result = self.svc.commit(batch, TODAY)
        self.assertEqual(result["settlements"], 1)
        s = Settlement.objects.get(group=self.group)
        # 10 USD * 83.50 * 100 = 83500 paise (previously booked as 1000 paise / INR 1:1)
        self.assertEqual(s.amount_minor, 83_500)
        self.assertEqual(s.from_person_id, self.rohan.id)
        self.assertEqual(s.to_person_id, self.aisha.id)
