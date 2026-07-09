"""Seed documented FX rates.

USD->INR rate is a DOCUMENTED ASSUMPTION (DECISIONS.md D4): we do not call a live API.
The Goa trip spend (USD) is in March 2026; we use a single effective-from-2026-01-01 rate
so every trip date resolves to it. To change the rate live, edit the fx_rate row in /admin.
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.expenses.models import FxRate

# (currency, rate_to_base, effective_date)
SEED_RATES = [
    ("USD", "83.50", date(2026, 1, 1)),
]


class Command(BaseCommand):
    help = "Seed documented FX rates (idempotent)."

    def handle(self, *args, **options):
        for currency, rate, eff in SEED_RATES:
            obj, created = FxRate.objects.get_or_create(
                currency=currency, effective_date=eff,
                defaults={"rate_to_base": rate},
            )
            verb = "created" if created else "exists"
            self.stdout.write(f"{verb}: 1 {currency} = {obj.rate_to_base} INR (from {eff})")
