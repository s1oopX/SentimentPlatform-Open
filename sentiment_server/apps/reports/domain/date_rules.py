from datetime import timedelta

from django.utils import timezone

from apps.reports.application.errors import ReportApplicationError


def resolve_report_dates(*, report_type, start_date=None, end_date=None):
    if start_date and end_date:
        return start_date, end_date

    today = timezone.localdate()
    if report_type == "daily":
        return today, today
    if report_type == "weekly":
        return today - timedelta(days=today.weekday()), today
    if report_type == "monthly":
        return today.replace(day=1), today

    raise ReportApplicationError(
        "当前报告类型需要显式提供开始日期和结束日期", status_code=400
    )
