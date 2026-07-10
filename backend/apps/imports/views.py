from datetime import date

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.views import owned_group

from .models import Anomaly, ImportBatch
from .services.import_service import (AlreadyCommitted, CommitBlocked,
                                      ImportService)
from .services.parser import ParseError
from .services.roster import apply_roster, scan_names


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB — bounds memory before we read the file


def _owned_batch(user, batch_id):
    return get_object_or_404(ImportBatch, pk=batch_id, group__created_by=user)


def _get_upload(request):
    """Return (upload, error_response). Rejects missing / oversized files before read()."""
    upload = request.FILES.get("file")
    if upload is None:
        return None, Response({"detail": "no file provided"}, status=400)
    if upload.size and upload.size > MAX_UPLOAD_BYTES:
        return None, Response({"detail": "file too large (max 5 MB)"},
                              status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    return upload, None


class ImportScanRosterView(APIView):
    """Propose a roster from an uploaded sheet without persisting anything."""

    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "imports"

    def post(self, request, group_id):
        group = owned_group(request.user, group_id)
        upload, err = _get_upload(request)
        if err:
            return err
        try:
            return Response(scan_names(upload.read(), upload.name, group))
        except ParseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class ImportApplyRosterView(APIView):
    """Create the user-confirmed people / memberships / aliases before import."""

    def post(self, request, group_id):
        group = owned_group(request.user, group_id)
        raw_start = request.data.get("start_date")
        try:
            start_date = date.fromisoformat(raw_start) if raw_start else timezone.localdate()
        except (TypeError, ValueError):
            return Response({"detail": "invalid start_date"}, status=400)
        people = request.data.get("people") or []
        with transaction.atomic():
            result = apply_roster(group, start_date, people)
        return Response(result, status=status.HTTP_201_CREATED)


class ImportUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "imports"

    def post(self, request, group_id):
        group = owned_group(request.user, group_id)
        upload, err = _get_upload(request)
        if err:
            return err
        svc = ImportService()
        try:
            batch = svc.ingest(group, upload.name, upload.read(), user=request.user)
        except ParseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
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
        except (CommitBlocked, AlreadyCommitted) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result)
