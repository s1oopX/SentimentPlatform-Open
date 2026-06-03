from apps.reports.models import Report


def get_user_report(*, user, report_id):
    return Report.objects.filter(pk=report_id, user=user).first()


def list_user_reports(*, user):
    return Report.objects.filter(user=user)
