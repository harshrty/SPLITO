from django.contrib import admin

from .models import Anomaly, ImportBatch, StagedRow


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "group", "status", "uploaded_at")
    list_filter = ("status",)


@admin.register(StagedRow)
class StagedRowAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "row_number")


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "staged_row", "anomaly_type", "severity",
                    "proposed_action", "status")
    list_filter = ("severity", "status", "anomaly_type")
