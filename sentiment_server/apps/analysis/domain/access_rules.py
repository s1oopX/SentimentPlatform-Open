from apps.analysis.application.errors import AnalysisApplicationError


ANALYST_ALLOWED_ROLES = ("analyst", "admin")


def has_analyst_access(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) in ANALYST_ALLOWED_ROLES
    )


def ensure_analyst_access(*, user):
    if not has_analyst_access(user):
        raise AnalysisApplicationError("权限不足", 403)
