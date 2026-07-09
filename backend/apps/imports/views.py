from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.views import owned_group

from .models import Anomaly, ImportBatch
from .services.import_service import CommitBlocked, ImportService


def _owned_batch(user, batch_id):
    return get_object_or_404(ImportBatch, pk=batch_id, group__created_by=user)


class ImportUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, group_id):
        group = owned_group(request.user, group_id)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "no file provided"}, status=400)
        svc = ImportService()
        batch = svc.ingest(group, upload.name, upload.read(), user=request.user)
        svc.run_detectors(batch, timezone.localdate())
        return Response({"batch_id": batch.id, "report": svc.report(batch)},
                        status=status.HTTP_201_CREATED)


class ImportReportView(APIView):
    def get(self, request, batch_id):
        batch = _owned_batch(request.user, batch_id)
        return Response({"batch_id": batch.id, "status": batch.status,
                         "report": ImportService().report(batch)})


class AnomalyResolveView(APIView):
    def post(self, request, anomaly_id):
        anomaly = get_object_or_404(Anomaly, pk=anomaly_id, batch__group__created_by=request.user)
        new_status = request.data.get("status")
        if new_status not in ("approved", "rejected", "edited"):
            return Response({"detail": "status must be approved/rejected/edited"}, status=400)
        ImportService().resolve(anomaly, new_status, request.data.get("resolved_value"), request.user)
        return Response({"id": anomaly.id, "status": anomaly.status})


class ImportCommitView(APIView):
    def post(self, request, batch_id):
        batch = _owned_batch(request.user, batch_id)
        try:
            result = ImportService().commit(batch, timezone.localdate(), user=request.user)
        except CommitBlocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result)
