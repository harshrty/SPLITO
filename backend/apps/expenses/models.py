"""Ledger models — maps SCOPE.md Layer B."""
from django.db import models

CURRENCIES = ["INR", "USD"]


class FxRate(models.Model):
    currency = models.CharField(max_length=3)
    rate_to_base = models.DecimalField(max_digits=12, decimal_places=6)
    effective_date = models.DateField()

    class Meta:
        db_table = "fx_rate"
        constraints = [
            models.UniqueConstraint(fields=["currency", "effective_date"], name="uq_fx_currency_date"),
            models.CheckConstraint(check=models.Q(rate_to_base__gt=0), name="fx_rate_positive"),
            models.CheckConstraint(check=models.Q(currency__in=CURRENCIES), name="fx_currency_valid"),
        ]

    def __str__(self):
        return f"{self.currency}@{self.effective_date}={self.rate_to_base}"


class Expense(models.Model):
    SPLIT_TYPES = [("equal", "equal"), ("unequal", "unequal"),
                   ("percentage", "percentage"), ("share", "share")]
    STATUSES = [("active", "active"), ("void", "void")]

    group = models.ForeignKey("groups.ExpenseGroup", on_delete=models.CASCADE, related_name="expenses")
    spent_on = models.DateField()
    description = models.CharField(max_length=200)
    # NOT NULL: a committed expense always has a resolved payer (missing-payer stays in quarantine)
    paid_by = models.ForeignKey("groups.Person", on_delete=models.RESTRICT, related_name="expenses_paid")
    original_amount_minor = models.BigIntegerField()          # paise; may be negative (refund)
    original_currency = models.CharField(max_length=3)
    amount_base_minor = models.BigIntegerField()              # converted to INR paise
    fx_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    fx_rate_source = models.CharField(max_length=100, null=True, blank=True)
    split_type = models.CharField(max_length=12, choices=SPLIT_TYPES)
    status = models.CharField(max_length=8, choices=STATUSES, default="active")
    notes = models.CharField(max_length=500, null=True, blank=True)
    import_batch = models.ForeignKey(
        "imports.ImportBatch", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="expenses",
    )
    source_row_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expense"
        indexes = [
            models.Index(fields=["group", "spent_on"], name="ix_expense_group_date"),
            models.Index(fields=["paid_by"], name="ix_expense_payer"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(original_amount_minor__gte=-1_000_000_000)
                & models.Q(original_amount_minor__lte=10_000_000_000),
                name="expense_amount_range",
            ),
            models.CheckConstraint(check=models.Q(original_currency__in=CURRENCIES), name="expense_currency_valid"),
            models.CheckConstraint(check=models.Q(fx_rate__gt=0), name="expense_fx_positive"),
        ]

    def __str__(self):
        return f"{self.spent_on} {self.description} ({self.amount_base_minor}p)"


class ExpenseShare(models.Model):
    """One split line per participant. Sum(computed_owed_minor) == expense.amount_base_minor."""

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="shares")
    person = models.ForeignKey("groups.Person", on_delete=models.RESTRICT, related_name="shares")
    share_input = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # NULL for equal
    computed_owed_minor = models.BigIntegerField()

    class Meta:
        db_table = "expense_share"
        indexes = [models.Index(fields=["person"], name="ix_share_person")]
        constraints = [
            models.UniqueConstraint(fields=["expense", "person"], name="uq_share_expense_person"),
            models.CheckConstraint(
                check=models.Q(share_input__isnull=True) | models.Q(share_input__gte=0),
                name="share_input_nonneg",
            ),
        ]


class Settlement(models.Model):
    """A payment/transfer — NOT an expense. INR-only (base currency)."""

    ORIGINS = [("manual", "manual"), ("reclassified_from_import", "reclassified_from_import")]

    group = models.ForeignKey("groups.ExpenseGroup", on_delete=models.CASCADE, related_name="settlements")
    from_person = models.ForeignKey("groups.Person", on_delete=models.RESTRICT, related_name="settlements_sent")
    to_person = models.ForeignKey("groups.Person", on_delete=models.RESTRICT, related_name="settlements_received")
    amount_minor = models.BigIntegerField()
    settled_on = models.DateField()
    note = models.CharField(max_length=300, null=True, blank=True)
    origin = models.CharField(max_length=24, choices=ORIGINS, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settlement"
        indexes = [models.Index(fields=["group"], name="ix_settlement_group")]
        constraints = [
            models.CheckConstraint(check=models.Q(amount_minor__gt=0), name="settlement_amount_positive"),
            models.CheckConstraint(check=~models.Q(from_person=models.F("to_person")), name="settlement_no_self"),
        ]
