"""End-to-end import test against the REAL provided xlsx (no hand-editing)."""
from datetime import date
from pathlib import Path

from django.test import TestCase

from apps.accounts.models import User
from apps.expenses.models import Expense, FxRate, Settlement
from apps.groups.models import ExpenseGroup, Membership, Person, PersonAlias
from apps.imports.models import StagedRow
from apps.imports.services.import_service import ImportService

XLSX = Path(__file__).resolve().parents[3].parent / "EXPENSE FILE" / "expenses_export assigbment annex.xlsx"
TODAY = date(2026, 7, 9)


class ImportPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="host@flat.com", display_name="Host", password="strongpass123")
        self.group = ExpenseGroup.objects.create(name="Flat 4B", created_by=self.user)
        # people (as the user would set up before importing)
        self.people = {}
        for name in ["Aisha", "Rohan", "Priya", "Meera", "Sam"]:
            self.people[name] = Person.objects.create(group=self.group, canonical_name=name)
        self.people["Dev"] = Person.objects.create(group=self.group, canonical_name="Dev", is_guest=True)
        # alias for the messy "Priya S"
        PersonAlias.objects.create(group=self.group, person=self.people["Priya"], raw_alias="Priya S")
        # memberships with the real timeline
        for name in ["Aisha", "Rohan", "Priya"]:
            Membership.objects.create(group=self.group, person=self.people[name], joined_on=date(2026, 2, 1))
        Membership.objects.create(group=self.group, person=self.people["Meera"],
                                  joined_on=date(2026, 2, 1), left_on=date(2026, 3, 31))
        Membership.objects.create(group=self.group, person=self.people["Sam"], joined_on=date(2026, 4, 8))
        FxRate.objects.create(currency="USD", rate_to_base="83.50", effective_date=date(2026, 1, 1))
        self.svc = ImportService()

    def _ingest_and_detect(self):
        batch = self.svc.ingest(self.group, XLSX.name, XLSX.read_bytes(), user=self.user)
        self.svc.run_detectors(batch, TODAY)
        return batch

    def test_stages_all_rows(self):
        batch = self.svc.ingest(self.group, XLSX.name, XLSX.read_bytes())
        self.assertEqual(StagedRow.objects.filter(batch=batch).count(), 42)

    def test_detects_the_anomaly_catalog(self):
        batch = self._ingest_and_detect()
        found = set(batch.anomalies.values_list("anomaly_type", flat=True))
        # the assignment promises "at least 12"; assert the key ones are caught
        expected = {
            "exact_dup", "fuzzy_dup", "pct_not_100", "missing_payer", "missing_currency",
            "negative_amount", "zero_amount", "sub_unit_amount", "type_detail_conflict",
            "out_of_bounds_date", "ex_member", "settlement_as_expense", "name_alias", "non_member",
        }
        missing = expected - found
        self.assertFalse(missing, f"detectors missed: {missing}")
        self.assertGreaterEqual(len(found), 12)

    def test_commit_gate_blocks_until_resolved(self):
        from apps.imports.services.import_service import CommitBlocked
        batch = self._ingest_and_detect()
        with self.assertRaises(CommitBlocked):
            self.svc.commit(batch, TODAY)

    def test_commit_produces_ledger(self):
        batch = self._ingest_and_detect()
        # approve every pending anomaly (the reviewer's decisions)
        for a in batch.anomalies.filter(status="pending"):
            self.svc.resolve(a, "approved")
        result = self.svc.commit(batch, TODAY)
        # settlements: "Rohan paid Aisha back" + "Sam deposit share"
        self.assertGreaterEqual(result["settlements"], 2)
        self.assertGreater(result["created"], 5)
        self.assertGreater(Expense.objects.filter(group=self.group).count(), 5)
        self.assertGreaterEqual(Settlement.objects.filter(group=self.group).count(), 2)
        # every imported expense reconciles: shares sum to the base amount
        for e in Expense.objects.filter(group=self.group).prefetch_related("shares"):
            self.assertEqual(sum(s.computed_owed_minor for s in e.shares.all()),
                             e.amount_base_minor, f"expense {e.id} shares don't reconcile")
        self.assertEqual(batch.status, "committed")
