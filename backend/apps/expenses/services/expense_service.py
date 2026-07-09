"""ExpenseService — validate, convert, split, and persist an expense atomically.

Shared by the manual create flow (Step 7) and the import commit (Step 8): same
validation, same SplitEngine, same CurrencyService — the importer is just a
deferred, human-gated version of this.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.groups.models import Person
from apps.groups.services import MembershipService

from ..models import Expense, ExpenseShare
from .currency import CurrencyService
from .split_engine import SplitError, compute


class ExpenseValidationError(ValueError):
    """Raised when an expense fails domain validation (bad payer/participant/date/split)."""


class ExpenseService:
    def __init__(self):
        self.currency = CurrencyService()
        self.membership = MembershipService()

    @transaction.atomic
    def create(
        self,
        *,
        group,
        spent_on: date,
        description: str,
        paid_by_id: int,
        amount: Decimal,
        currency: str,
        split_type: str,
        participants: list[int],
        details: dict[int, Decimal] | None = None,
        notes: str | None = None,
        import_batch=None,
        source_row_number: int | None = None,
    ) -> Expense:
        group_person_ids = set(Person.objects.filter(group=group).values_list("id", flat=True))

        # payer + participants must belong to the group
        if paid_by_id not in group_person_ids:
            raise ExpenseValidationError("payer is not a member of this group")
        unknown = set(participants) - group_person_ids
        if unknown:
            raise ExpenseValidationError(f"participants not in group: {sorted(unknown)}")

        # temporal check: non-guest participants must be members on spent_on
        guests = set(Person.objects.filter(group=group, is_guest=True).values_list("id", flat=True))
        members_on = self.membership.members_on(group.id, spent_on)
        for pid in participants:
            if pid not in guests and pid not in members_on:
                raise ExpenseValidationError(f"person {pid} was not a member on {spent_on}")

        # convert currency, then split in integer paise
        conv = self.currency.to_base(amount, currency, spent_on)
        try:
            shares = compute(conv.amount_base_minor, split_type, participants, details)
        except SplitError as exc:
            raise ExpenseValidationError(str(exc)) from exc

        expense = Expense.objects.create(
            group=group, spent_on=spent_on, description=description,
            paid_by_id=paid_by_id,
            original_amount_minor=conv.original_amount_minor, original_currency=currency,
            amount_base_minor=conv.amount_base_minor,
            fx_rate=conv.fx_rate, fx_rate_source=conv.fx_rate_source,
            split_type=split_type, notes=notes,
            import_batch=import_batch, source_row_number=source_row_number,
        )
        ExpenseShare.objects.bulk_create([
            ExpenseShare(
                expense=expense, person_id=s.person_id,
                share_input=s.share_input, computed_owed_minor=s.computed_owed_minor,
            )
            for s in shares
        ])
        return expense
