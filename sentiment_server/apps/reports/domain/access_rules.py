from django.contrib.auth import get_user_model

from apps.reports.application.errors import ReportApplicationError


def resolve_live_report_role(*, user):
    if not user or not getattr(user, "pk", None):
        raise ReportApplicationError(
            "账号状态或权限已变更，无法继续生成此报表", status_code=403
        )

    user_model = get_user_model()
    live_user = user_model.objects.filter(pk=user.pk).only("role", "status").first()
    if not live_user or getattr(live_user, "status", 0) != 1:
        raise ReportApplicationError(
            "账号状态或权限已变更，无法继续生成此报表", status_code=403
        )

    return getattr(live_user, "role", "")
