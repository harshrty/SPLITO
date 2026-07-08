"""Import & quarantine models — maps SCOPE.md Layer C."""
from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    STATUSES = [("pending", "pending"), ("committed", "committed")]

    group = models.ForeignKey("groups.ExpenseGroup", on_delete=models.CASCADE, related_name="import_batches")
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=STATUSES, default="pending")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "import_batch"

    def __str__(self):
        return f"batch#{self.pk} {self.filename} ({self.status})"


class StagedRow(models.Model):
    """The raw CSV row, stored verbatim. Never validated — import never crashes."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.IntegerField()
    raw_json = models.JSONField()

    class Meta:
        db_table = "staged_row"
        indexes = [models.Index(fields=["batch"], name="ix_staged_batch")]


class Anomaly(models.Model):
    """One detected problem + its proposed fix + review status. The Import Report is a query over this."""

    ANOMALY_TYPES = [
        (t, t) for t in [
            "exact_dup", "fuzzy_dup", "pct_not_100", "unequal_sum_mismatch",
            "ambiguous_date", "out_of_bounds_date", "missing_payer", "missing_currency",
            "negative_amount", "zero_amount", "sub_unit_amount", "type_detail_conflict",
            "non_member", "ex_member", "settlement_as_expense", "name_alias",
        ]
    ]
    SEVERITIES = [("block", "block"), ("warn", "warn")]
    ACTIONS = [
        (a, a) for a in [
            "void_dup", "merge", "reclassify_settlement", "normalize_name",
            "convert_currency", "exclude_person", "request_input", "reject", "skip",
        ]
    ]
    STATUSES = [("pending", "pending"), ("approved", "approved"),
                ("rejected", "rejected"), ("edited", "edited")]

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="anomalies")
    staged_row = models.ForeignKey(
        StagedRow, null=True, blank=True, on_delete=models.CASCADE, related_name="anomalies",
    )
    anomaly_type = models.CharField(max_length=32, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=8, choices=SEVERITIES)
    detail = models.CharField(max_length=300)
    proposed_action = models.CharField(max_length=32, choices=ACTIONS)
    status = models.CharField(max_length=12, choices=STATUSES, default="pending")
    resolved_value = models.JSONField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "anomaly"
        indexes = [
            models.Index(fields=["batch"], name="ix_anomaly_batch"),
            models.Index(fields=["status"], name="ix_anomaly_status"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(severity__in=["block", "warn"]), name="anomaly_severity_valid"),
            models.CheckConstraint(
                check=models.Q(status__in=["pending", "approved", "rejected", "edited"]),
                name="anomaly_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.anomaly_type} ({self.severity}) row={self.staged_row_id}"
