import os
import logging
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.reports.application.errors import ReportApplicationError
from apps.reports.domain.artifact_rules import ensure_report_artifact_path_is_safe
from apps.reports.infra.audit_logs import write_report_download_log
from apps.reports.infra.selectors.reports import get_user_report
from apps.reports.models import Report, ReportStatus


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadReportRequestResult:
    report: Report
    artifact_path: Path
    filename: str


def download_report_request(*, user, report_id, request_ip):
    report = get_user_report(user=user, report_id=report_id)
    if report is None:
        raise ReportApplicationError("报告不存在", status_code=404)

    if report.status != ReportStatus.COMPLETED or not report.file_path:
        raise ReportApplicationError("报告尚未生成", status_code=400)

    resolved_path = ensure_report_artifact_path_is_safe(
        report_root=settings.REPORT_ROOT,
        file_path=report.file_path,
    )
    if (
        resolved_path is None
        or not resolved_path.exists()
        or not resolved_path.is_file()
    ):
        raise ReportApplicationError("报告文件不存在", status_code=404)

    try:
        write_report_download_log(report=report, user=user, request_ip=request_ip)
    except Exception:
        logger.exception(
            "报告下载审计日志写入失败: user_id=%s report_id=%s",
            getattr(user, "id", None),
            report_id,
        )

    return DownloadReportRequestResult(
        report=report,
        artifact_path=resolved_path,
        filename=os.path.basename(resolved_path),
    )
