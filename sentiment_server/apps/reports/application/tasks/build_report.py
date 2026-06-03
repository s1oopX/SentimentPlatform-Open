import logging

from django.db import OperationalError, InterfaceError

from apps.reports.application.report_building import (
    build_report_queryset,
    build_report_summary,
)
from apps.reports.infra.file_rendering import render_report_file


logger = logging.getLogger(__name__)


def claim_report_processing(report_id):
    from apps.reports.infra.tasks.build_report import _claim_report_processing

    return _claim_report_processing(report_id)


def finalize_report_success(
    *, report_id, processing_token, summary, file_path, file_size
):
    from apps.reports.infra.tasks.build_report import _finalize_report_success

    return _finalize_report_success(
        report_id=report_id,
        processing_token=processing_token,
        summary=summary,
        file_path=file_path,
        file_size=file_size,
    )


def finalize_report_failure(*, report_id, processing_token):
    from apps.reports.infra.tasks.build_report import _finalize_report_failure

    return _finalize_report_failure(
        report_id=report_id,
        processing_token=processing_token,
    )


def cleanup_orphan_report_file(*, report_id, file_path):
    from apps.reports.infra.tasks.build_report import _cleanup_orphan_report_file

    return _cleanup_orphan_report_file(report_id=report_id, file_path=file_path)


def get_report_file_size(file_path):
    from apps.reports.infra.tasks.build_report import get_report_file_size as impl

    return impl(file_path)


def build_report(report_id):
    report = claim_report_processing(report_id)
    if report is None:
        return

    processing_token = report.processing_token
    file_path = None

    try:
        results = build_report_queryset(
            user=report.user,
            request_params=report.request_params or {},
            start_date=report.start_date,
            end_date=report.end_date,
        )
        summary = build_report_summary(results)
        file_path = render_report_file(
            report=report,
            user=report.user,
            results=results,
            summary=summary,
        )
        file_size = get_report_file_size(file_path)
        finalized = finalize_report_success(
            report_id=report_id,
            processing_token=processing_token,
            summary=summary,
            file_path=file_path,
            file_size=file_size,
        )
        if not finalized:
            cleanup_orphan_report_file(
                report_id=report_id,
                file_path=file_path,
            )
    except (OperationalError, InterfaceError):
        # Transient database errors: let them propagate so Celery
        # autoretry_for can retry the task instead of permanently
        # marking the report as failed.
        logger.warning(
            "Transient DB error in report %s, will be retried by Celery",
            report_id,
            exc_info=True,
        )
        raise
    except Exception:
        logger.exception("报告生成失败: report_id=%s", report_id)
        cleanup_orphan_report_file(
            report_id=report_id,
            file_path=file_path,
        )
        finalize_report_failure(
            report_id=report_id,
            processing_token=processing_token,
        )
