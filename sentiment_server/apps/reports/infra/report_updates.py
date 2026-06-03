from django.db.models import F
from django.utils import timezone

from apps.reports.models import Report, ReportStatus


def mark_report_enqueue_attempt(report_id, *, succeeded, error_message=""):
    update_fields = {
        "enqueue_attempts": F("enqueue_attempts") + 1,
        "last_enqueue_attempt_at": timezone.now(),
        "last_enqueue_error": "" if succeeded else error_message[:500],
    }
    if succeeded:
        update_fields["status"] = ReportStatus.PENDING
    else:
        update_fields["status"] = ReportStatus.FAILED

    return Report.objects.filter(
        pk=report_id,
        status=ReportStatus.PENDING_ENQUEUE,
    ).update(**update_fields)
