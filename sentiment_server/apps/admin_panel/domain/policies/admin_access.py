from apps.admin_panel.domain.errors import AdminPanelDomainError


def is_admin_access_allowed(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", "") == "admin"
    )


def ensure_admin_access(
    *, user_role, is_authenticated, error_cls=AdminPanelDomainError
):
    if not (is_authenticated and user_role == "admin"):
        raise error_cls("permission_denied", "权限不足", status_code=403)
    return True


def require_admin_access(user, *, error_cls=AdminPanelDomainError):
    ensure_admin_access(
        user_role=getattr(user, "role", ""),
        is_authenticated=getattr(user, "is_authenticated", False),
        error_cls=error_cls,
    )
    return user
