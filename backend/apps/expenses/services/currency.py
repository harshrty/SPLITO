"""CurrencyService — convert an amount to base INR paise and snapshot the rate used.

Design (DECISIONS.md D4):
- Rates come from the `fx_rate` table, effective by date (not a live API).
- The rate used is snapshotted onto the expense, so editing the rate table later never
  silently rewrites historical conversions.
- Major → minor uses HALF_UP rounding (this is where 899.995 becomes ₹900.00 = 90000 paise).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.expenses.models import FxRate

BASE_CURRENCY = "INR"
MINOR = Decimal(100)  # paise


class CurrencyError(ValueError):
    """Raised when no exchange rate is available for a requested currency/date."""


@dataclass(frozen=True)
class Conversion:
    original_amount_minor: int
    amount_base_minor: int
    fx_rate: Decimal
    fx_rate_source: str


def _to_minor(major: Decimal) -> int:
    """₹700.00 -> 70000 paise; 899.995 -> 90000 (HALF_UP)."""
    return int((major * MINOR).quantize(Decimal(1), rounding=ROUND_HALF_UP))


class CurrencyService:
    base = BASE_CURRENCY

    def to_base(self, amount: Decimal | str | int, currency: str, on: date) -> Conversion:
        amount = Decimal(str(amount))
        original_minor = _to_minor(amount)
        if currency == self.base:
            return Conversion(original_minor, original_minor, Decimal(1), "identity")
        rate, source = self._lookup(currency, on)
        base_minor = _to_minor(amount * rate)
        return Conversion(original_minor, base_minor, rate, source)

    def _lookup(self, currency: str, on: date) -> tuple[Decimal, str]:
        row = (
            FxRate.objects.filter(currency=currency, effective_date__lte=on)
            .order_by("-effective_date")
            .first()
        )
        if row is None:
            raise CurrencyError(f"no fx rate for {currency} on/before {on}")
        return row.rate_to_base, f"fx_rate#{row.id}@{row.effective_date}"
