import logging
from dataclasses import dataclass

from django.db import transaction

from apps.reports.application.errors import ReportApplicationError
from apps.reports.domain.date_rules import (
    resolve_report_dates as resolve_report_request_dates,
)
from apps.reports.infra.audit_logs import write_report_export_log
from apps.reports.infra.report_delivery import enqueue_report_delivery
from apps.reports.models import Report, ReportStatus


logger = logging.getLogger(__name__)
REPORT_CREATED_MESSAGE = "报表任务已创建，后台正在处理提交"


@dataclass(frozen=True)
class GenerateReportRequestResult:
    message: str
    report: Report


def generate_report_request(
    *,
    user,
    report_type,
    report_format,
    start_date,
    end_date,
    request_params,
    request_ip,
):
    try:
        resolved_start_date, resolved_end_date = resolve_report_request_dates(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
        )
    except ReportApplicationError:
        raise
    except ValueError as exc:
        raise ReportApplicationError(str(exc), status_code=400) from exc

    try:
        with transaction.atomic():
            report = Report.objects.create(
                user=user,
                report_type=report_type,
                report_format=report_format,
                start_date=resolved_start_date,
                end_date=resolved_end_date,
                status=ReportStatus.PENDING_ENQUEUE,
                request_params=request_params,
            )
            transaction.on_commit(
                lambda report_id=report.id: enqueue_report_delivery(report_id)
            )
    except Exception as exc:
        logger.exception(
            "报表任务创建失败: user_id=%s report_type=%s",
            getattr(user, "id", None),
            report_type,
        )
        raise ReportApplicationError(
            "报表任务创建失败，请稍后重试", status_code=500
        ) from exc

    try:
        write_report_export_log(
            user=user,
            report_type=report_type,
            report_id=report.id,
            request_ip=request_ip,
        )
    except Exception:
        logger.exception(
            "报告导出审计日志写入失败: user_id=%s report_id=%s report_type=%s",
            getattr(user, "id", None),
            report.id,
            report_type,
        )

    report.refresh_from_db()
    return GenerateReportRequestResult(
        message=REPORT_CREATED_MESSAGE,
        report=report,
    )
