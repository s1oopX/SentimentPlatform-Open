from apps.reports.infra.selectors.reports import list_user_reports


def list_reports_query(*, user, report_type="", status=""):
    reports = list_user_reports(user=user)

    if report_type:
        reports = reports.filter(report_type=report_type)

    if status:
        reports = reports.filter(status=status)

    return reports.order_by("-created_at")
