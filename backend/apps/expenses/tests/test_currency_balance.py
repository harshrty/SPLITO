"""Tests for CurrencyService and BalanceService (need DB → TestCase)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.expenses.models import Expense, ExpenseShare, FxRate, Settlement
from apps.expenses.services.balances import BalanceService
from apps.expenses.services.currency import CurrencyError, CurrencyService
from apps.groups.models import ExpenseGroup, Person


class CurrencyServiceTests(TestCase):
    def setUp(self):
        self.svc = CurrencyService()
        FxRate.objects.create(currency="USD", rate_to_base="83.50", effective_date=date(2026, 1, 1))

    def test_inr_is_identity(self):
        c = self.svc.to_base(Decimal("2340"), "INR", date(2026, 2, 3))
        self.assertEqual(c.amount_base_minor, 234_000)
        self.assertEqual(c.fx_rate, Decimal(1))
        self.assertEqual(c.fx_rate_source, "identity")

    def test_usd_converted_and_rate_snapshotted(self):
        # Goa villa 540 USD * 83.50 = ₹45090 = 4509000 paise
        c = self.svc.to_base(Decimal("540"), "USD", date(2026, 3, 9))
        self.assertEqual(c.amount_base_minor, 4_509_000)
        self.assertEqual(c.fx_rate, Decimal("83.50"))
        self.assertTrue(c.fx_rate_source.startswith("fx_rate#"))

    def test_sub_paisa_rounds_half_up(self):
        # Cylinder refill 899.995 -> ₹900.00
        c = self.svc.to_base(Decimal("899.995"), "INR", date(2026, 2, 15))
        self.assertEqual(c.amount_base_minor, 90_000)

    def test_missing_rate_raises(self):
        with self.assertRaises(CurrencyError):
            self.svc.to_base(Decimal("10"), "USD", date(2025, 12, 31))  # before any rate


class BalanceServiceTests(TestCase):
    def setUp(self):
        self.svc = BalanceService()
        self.g = ExpenseGroup.objects.create(name="Flat")
        self.aisha = Person.objects.create(group=self.g, canonical_name="Aisha")
        self.rohan = Person.objects.create(group=self.g, canonical_name="Rohan")
        self.priya = Person.objects.create(group=self.g, canonical_name="Priya")
        self.meera = Person.objects.create(group=self.g, canonical_name="Meera")

    def _rent(self):
        # Aisha pays ₹48000, split equally 4 ways (₹12000 each)
        e = Expense.objects.create(
            group=self.g, spent_on=date(2026, 2, 1), description="rent",
            paid_by=self.aisha, original_amount_minor=4_800_000, original_currency="INR",
            amount_base_minor=4_800_000, split_type="equal",
        )
        for p in (self.aisha, self.rohan, self.priya, self.meera):
            ExpenseShare.objects.create(expense=e, person=p, computed_owed_minor=1_200_000)
        return e

    def test_balances_before_settlement(self):
        self._rent()
        net = self.svc.net_balances(self.g.id)
        self.assertEqual(net[self.aisha.id], 3_600_000)   # owed ₹36000
        self.assertEqual(net[self.rohan.id], -1_200_000)  # owes ₹12000
        self.assertEqual(sum(net.values()), 0)            # always sums to zero

    def test_settlement_signs_are_correct(self):
        # REGRESSION for the verification bug: Rohan pays Aisha ₹5000.
        # Correct: Rohan owes ₹7000, Aisha owed ₹31000 (NOT -17000 / +41000).
        self._rent()
        Settlement.objects.create(
            group=self.g, from_person=self.rohan, to_person=self.aisha,
            amount_minor=500_000, settled_on=date(2026, 2, 25),
        )
        net = self.svc.net_balances(self.g.id)
        self.assertEqual(net[self.rohan.id], -700_000)   # owes ₹7000
        self.assertEqual(net[self.aisha.id], 3_100_000)  # owed ₹31000
        self.assertEqual(sum(net.values()), 0)

    def test_void_expense_excluded(self):
        e = self._rent()
        e.status = "void"
        e.save()
        net = self.svc.net_balances(self.g.id)
        self.assertEqual(net.get(self.aisha.id, 0), 0)

    def test_simplify_produces_valid_transfers(self):
        self._rent()
        net = self.svc.net_balances(self.g.id)
        transfers = self.svc.simplify(net)
        # 3 debtors each owe ₹12000 to the one creditor (Aisha) -> 3 transfers
        self.assertEqual(len(transfers), 3)
        self.assertTrue(all(t.to_person_id == self.aisha.id for t in transfers))
        self.assertEqual(sum(t.amount_minor for t in transfers), 3_600_000)

    def test_ledger_itemizes_shares(self):
        self._rent()
        rows = self.svc.ledger_for(self.rohan.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["owed_minor"], 1_200_000)
        self.assertFalse(rows[0]["paid_by_me"])
