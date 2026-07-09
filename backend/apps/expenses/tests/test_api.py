"""Integration tests for groups + expenses + settlements + balances APIs."""
from datetime import date

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.expenses.models import FxRate
from apps.groups.models import ExpenseGroup, Membership, Person


class ApiFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="me@flat.com", display_name="Me", password="strongpass123")
        self.client.force_authenticate(self.user)
        FxRate.objects.create(currency="USD", rate_to_base="83.50", effective_date=date(2026, 1, 1))
        self.group = ExpenseGroup.objects.create(name="Flat 4B", created_by=self.user)
        self.aisha = Person.objects.create(group=self.group, canonical_name="Aisha")
        self.rohan = Person.objects.create(group=self.group, canonical_name="Rohan")
        self.meera = Person.objects.create(group=self.group, canonical_name="Meera")
        # Aisha & Rohan are ongoing; Meera left end of March
        for p in (self.aisha, self.rohan):
            Membership.objects.create(group=self.group, person=p, joined_on=date(2026, 2, 1))
        Membership.objects.create(group=self.group, person=self.meera,
                                  joined_on=date(2026, 2, 1), left_on=date(2026, 3, 31))

    def _create_expense(self, **overrides):
        payload = {
            "spent_on": "2026-02-01", "description": "rent", "paid_by": self.aisha.id,
            "amount": "48000", "currency": "INR", "split_type": "equal",
            "participants": [self.aisha.id, self.rohan.id, self.meera.id],
        }
        payload.update(overrides)
        return self.client.post(f"/api/groups/{self.group.id}/expenses/", payload, format="json")

    def test_create_equal_expense_makes_shares(self):
        resp = self._create_expense()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data["shares"]), 3)
        self.assertEqual(sum(s["computed_owed_minor"] for s in resp.data["shares"]), 4_800_000)

    def test_ex_member_after_leave_rejected(self):
        # Meera left Mar 31 → an April 2 expense including her must be rejected (Sam's rule)
        resp = self._create_expense(spent_on="2026-04-02",
                                    participants=[self.aisha.id, self.rohan.id, self.meera.id])
        self.assertEqual(resp.status_code, 400)
        self.assertIn("was not a member", str(resp.data))

    def test_percentage_over_100_rejected(self):
        resp = self._create_expense(
            split_type="percentage",
            participants=[self.aisha.id, self.rohan.id, self.meera.id],
            details={str(self.aisha.id): 40, str(self.rohan.id): 40, str(self.meera.id): 40},
        )
        self.assertEqual(resp.status_code, 400)

    def test_usd_expense_converted(self):
        resp = self._create_expense(spent_on="2026-03-09", description="Goa villa",
                                    amount="540", currency="USD",
                                    participants=[self.aisha.id, self.rohan.id])
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["amount_base_minor"], 4_509_000)  # 540 * 83.50 * 100

    def test_balances_and_simplify_and_settlement(self):
        self._create_expense()  # Aisha paid 48000, 3-way → 16000 each
        # balances
        bal = self.client.get(f"/api/groups/{self.group.id}/balances/").data
        net = {b["person_id"]: b["net_minor"] for b in bal}
        self.assertEqual(net[self.aisha.id], 3_200_000)   # owed 32000
        self.assertEqual(net[self.rohan.id], -1_600_000)  # owes 16000
        # settle: Rohan pays Aisha 16000
        s = self.client.post(f"/api/groups/{self.group.id}/settlements/", {
            "from_person": self.rohan.id, "to_person": self.aisha.id,
            "amount_minor": 1_600_000, "settled_on": "2026-04-01",
        }, format="json")
        self.assertEqual(s.status_code, 201, s.data)
        net2 = {b["person_id"]: b["net_minor"] for b in
                self.client.get(f"/api/groups/{self.group.id}/balances/").data}
        self.assertEqual(net2[self.rohan.id], 0)  # settled

    def test_ledger_itemizes(self):
        self._create_expense()
        rows = self.client.get(f"/api/people/{self.rohan.id}/ledger/").data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["owed_minor"], 1_600_000)

    def test_groups_scoped_to_owner(self):
        other = User.objects.create_user(email="x@flat.com", display_name="X", password="strongpass123")
        self.client.force_authenticate(other)
        resp = self.client.get(f"/api/groups/{self.group.id}/expenses/")
        self.assertEqual(resp.status_code, 404)  # not their group
