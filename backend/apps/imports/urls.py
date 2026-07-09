from django.urls import path

from .views import (AnomalyResolveView, ImportCommitView, ImportReportView,
                    ImportUploadView)

urlpatterns = [
    path("groups/<int:group_id>/import/", ImportUploadView.as_view(), name="import-upload"),
    path("import/<int:batch_id>/report/", ImportReportView.as_view(), name="import-report"),
    path("import/anomalies/<int:anomaly_id>/resolve/", AnomalyResolveView.as_view(), name="anomaly-resolve"),
    path("import/<int:batch_id>/commit/", ImportCommitView.as_view(), name="import-commit"),
]
