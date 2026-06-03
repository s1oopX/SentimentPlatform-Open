import os
from pathlib import Path
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.db import OperationalError, InterfaceError, transaction
from django.utils import timezone

from apps.reports.application.tasks.build_report import (
    build_report as build_report_use_case,
)
from apps.reports.models import Report, ReportStatus


def _resolve_report_artifact_path(file_path):
    if not file_path:
        return None

    report_root = Path(settings.REPORT_ROOT).resolve()
    candidate = Path(file_path).resolve()
    try:
        candidate.relative_to(report_root)
    except ValueError:
        return None

    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def _report_artifact_is_usable(report):
    return _resolve_report_artifact_path(report.file_path) is not None


def _cleanup_orphan_report_file(*, report_id, file_path):
    candidate = _resolve_report_artifact_path(file_path)
    if candidate is None:
        return False

    with transaction.atomic():
        report = Report.objects.select_for_update().get(pk=report_id)
        if report.file_path == str(candidate):
            return False

    try:
        candidate.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def _claim_report_processing(report_id):
    now = timezone.now()

    with transaction.atomic():
        report = (
            Report.objects.select_for_update().select_related("user").get(pk=report_id)
        )

        if report.status == ReportStatus.COMPLETED and _report_artifact_is_usable(
            report
        ):
            return None

        if report.status == ReportStatus.PROCESSING:
            return None

        if report.status not in (
            ReportStatus.PENDING_ENQUEUE,
            ReportStatus.PENDING,
            ReportStatus.COMPLETED,
        ):
            return None

        report.status = ReportStatus.PROCESSING
        report.processing_started_at = now
        report.processing_token = uuid4().hex
        report.save(
            update_fields=["status", "processing_started_at", "processing_token"]
        )
        return report


def _finalize_report_success(
    *, report_id, processing_token, summary, file_path, file_size
):
    with transaction.atomic():
        report = Report.objects.select_for_update().get(pk=report_id)
        if (
            report.status != ReportStatus.PROCESSING
            or report.processing_token != processing_token
        ):
            return False

        report.summary = summary
        report.file_path = file_path
        report.file_size = file_size
        report.status = ReportStatus.COMPLETED
        report.completed_at = timezone.now()
        report.save(
            update_fields=[
                "summary",
                "file_path",
                "file_size",
                "status",
                "completed_at",
            ]
        )
        return True


def _finalize_report_failure(*, report_id, processing_token):
    with transaction.atomic():
        report = Report.objects.select_for_update().get(pk=report_id)
        if (
            report.status != ReportStatus.PROCESSING
            or report.processing_token != processing_token
        ):
            return False

        report.summary = None
        report.status = ReportStatus.FAILED
        report.file_path = None
        report.file_size = 0
        report.completed_at = None
        report.save(
            update_fields=[
                "summary",
                "status",
                "file_path",
                "file_size",
                "completed_at",
            ]
        )
        return True


def get_report_file_size(file_path):
    return os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0


@shared_task(
    name="apps.reports.tasks.build_and_store_report",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=60,
    retry_backoff_max=300,
)
def build_and_store_report(report_id):
    return build_report_use_case(report_id)
