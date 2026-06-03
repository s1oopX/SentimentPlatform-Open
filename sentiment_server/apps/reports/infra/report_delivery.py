import logging

from apps.reports.application.user_messages import REPORT_ENQUEUE_FAILURE_MESSAGE
from apps.reports.infra.report_updates import mark_report_enqueue_attempt
from apps.reports.infra.tasks.build_report import (
    build_and_store_report as generate_report_task,
)


logger = logging.getLogger(__name__)


def enqueue_report_delivery(report_id):
    try:
        generate_report_task.delay(report_id)
    except Exception:
        logger.exception("报告任务提交失败: report_id=%s", report_id)
        mark_report_enqueue_attempt(
            report_id,
            succeeded=False,
            error_message=REPORT_ENQUEUE_FAILURE_MESSAGE,
        )
        return False

    mark_report_enqueue_attempt(report_id, succeeded=True)
    return True
