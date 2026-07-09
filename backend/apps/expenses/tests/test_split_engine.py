"""Unit tests for the SplitEngine. Pure logic → SimpleTestCase (no DB)."""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.expenses.services.split_engine import ShareLine, SplitError, compute


def owed(shares):
    return [s.computed_owed_minor for s in shares]


class EqualSplitTests(SimpleTestCase):
    def test_divisible_rent(self):
        # "February rent" ₹48000 equally among 4 → ₹12000 each
        shares = compute(4_800_000, "equal", [1, 2, 3, 4])
        self.assertEqual(owed(shares), [1_200_000] * 4)
        self.assertEqual(sum(owed(shares)), 4_800_000)
        self.assertIsNone(shares[0].share_input)  # equal stores no per-person input

    def test_indivisible_remainder_goes_to_first_by_id(self):
        # 10 paise among 3 → 4,3,3 (first participant by id gets the extra)
        shares = compute(10, "equal", [7, 3, 5])
        # sorted by id: 3,5,7 → remainder 1 to id=3
        by_id = {s.person_id: s.computed_owed_minor for s in shares}
        self.assertEqual(by_id, {3: 4, 5: 3, 7: 3})
        self.assertEqual(sum(owed(shares)), 10)

    def test_cylinder_refill_rounded_total(self):
        # "Cylinder refill" 899.995 is rounded to ₹900.00 upstream → 90000 paise / 4
        shares = compute(90_000, "equal", [1, 2, 3, 4])
        self.assertEqual(owed(shares), [22_500] * 4)
        self.assertEqual(sum(owed(shares)), 90_000)

    def test_negative_refund_divisible(self):
        # "Parasailing refund" -30 USD → assume -3000 base paise among 4
        shares = compute(-3_000, "equal", [1, 2, 3, 4])
        self.assertEqual(owed(shares), [-750] * 4)
        self.assertEqual(sum(owed(shares)), -3_000)

    def test_negative_with_remainder_still_reconciles(self):
        shares = compute(-101, "equal", [1, 2, 3, 4])
        self.assertEqual(sum(owed(shares)), -101)


class ShareSplitTests(SimpleTestCase):
    def test_scooter_rentals(self):
        # "Scooter rentals" ₹3600, shares Aisha1 Rohan2 Priya1 Dev2 (ids 1,2,3,4)
        shares = compute(360_000, "share", [1, 2, 3, 4],
                         {1: 1, 2: 2, 3: 1, 4: 2})
        by_id = {s.person_id: s.computed_owed_minor for s in shares}
        self.assertEqual(by_id, {1: 60_000, 2: 120_000, 3: 60_000, 4: 120_000})
        self.assertEqual(sum(owed(shares)), 360_000)

    def test_april_rent_uneven_weights(self):
        # "April rent" ₹48000, shares Aisha2 Rohan1 Priya1
        shares = compute(4_800_000, "share", [1, 2, 3], {1: 2, 2: 1, 3: 1})
        by_id = {s.person_id: s.computed_owed_minor for s in shares}
        self.assertEqual(by_id, {1: 2_400_000, 2: 1_200_000, 3: 1_200_000})
        self.assertEqual(sum(owed(shares)), 4_800_000)

    def test_zero_total_weight_rejected(self):
        with self.assertRaises(SplitError):
            compute(1000, "share", [1, 2], {1: 0, 2: 0})


class PercentageSplitTests(SimpleTestCase):
    def test_valid_percentages(self):
        shares = compute(144_000, "percentage", [1, 2, 3, 4],
                         {1: 30, 2: 30, 3: 20, 4: 20})
        self.assertEqual(sum(owed(shares)), 144_000)

    def test_pizza_110_percent_rejected(self):
        # "Pizza Friday" 30+30+30+20 = 110 → must fail hard (D2)
        with self.assertRaises(SplitError):
            compute(144_000, "percentage", [1, 2, 3, 4],
                    {1: 30, 2: 30, 3: 30, 4: 20})

    def test_percentage_remainder_reconciles(self):
        # 100 paise, 33/33/34 → sums to 100 exactly
        shares = compute(100, "percentage", [1, 2, 3], {1: Decimal("33.33"),
                                                        2: Decimal("33.33"),
                                                        3: Decimal("33.34")})
        self.assertEqual(sum(owed(shares)), 100)


class UnequalSplitTests(SimpleTestCase):
    def test_birthday_cake(self):
        # "Aisha birthday cake" ₹1500: Rohan 700; Priya 400; Meera 400
        shares = compute(150_000, "unequal", [2, 3, 4],
                         {2: 700, 3: 400, 4: 400})
        by_id = {s.person_id: s.computed_owed_minor for s in shares}
        self.assertEqual(by_id, {2: 70_000, 3: 40_000, 4: 40_000})
        self.assertEqual(sum(owed(shares)), 150_000)
        self.assertEqual(shares[0].share_input, Decimal("700"))

    def test_unequal_sum_mismatch_rejected(self):
        with self.assertRaises(SplitError):
            compute(150_000, "unequal", [2, 3, 4], {2: 700, 3: 400, 4: 300})

    def test_sub_paisa_input_rejected(self):
        with self.assertRaises(SplitError):
            compute(100_050, "unequal", [1, 2], {1: Decimal("500.255"), 2: 500.25})


class GuardTests(SimpleTestCase):
    def test_empty_participants(self):
        with self.assertRaises(SplitError):
            compute(1000, "equal", [])

    def test_details_must_match_participants(self):
        with self.assertRaises(SplitError):
            compute(1000, "share", [1, 2, 3], {1: 1, 2: 1})  # missing pid 3

    def test_unknown_split_type(self):
        with self.assertRaises(SplitError):
            compute(1000, "weird", [1, 2])

    def test_determinism_same_input_same_output(self):
        a = compute(100, "equal", [3, 1, 2])
        b = compute(100, "equal", [1, 2, 3])
        self.assertEqual(owed(a), owed(b))

    def test_invariant_across_many_sizes(self):
        # the core promise: shares always reconcile to the total, any size/amount
        for amount in [1, 7, 100, 899_99, 4_800_001, 1_000_003]:
            for n in range(1, 8):
                shares = compute(amount, "equal", list(range(1, n + 1)))
                self.assertEqual(sum(owed(shares)), amount,
                                 f"failed for amount={amount} n={n}")
