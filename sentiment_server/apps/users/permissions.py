from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated


class PublicUserPermission(AllowAny):
    """users 模块内的公开接口权限。"""


class AuthenticatedUserPermission(IsAuthenticated):
    """users 模块内的登录态权限。"""


class IsAdminUserRole(BasePermission):
    """仅允许管理员访问。"""

    message = "权限不足"

    def has_permission(self, request, _view):
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "role", "") == "admin"
        )


class IsAnalystOrAdmin(BasePermission):
    """仅允许分析师或管理员访问。"""

    message = "权限不足"

    def has_permission(self, request, _view):
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "role", "") in {"analyst", "admin"}
        )


class IsUserOrAdmin(BasePermission):
    """仅允许普通用户或管理员访问（分析师专注审核工作，不参与提交分析与生成个人报告）。"""

    message = "当前角色无权执行此操作"

    def has_permission(self, request, _view):
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "role", "") in {"user", "admin"}
        )


class IsSelfOrAdmin(BasePermission):
    """仅允许用户本人或管理员访问。"""

    message = "权限不足"

    def has_object_permission(self, request, _view, obj):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return getattr(user, "role", "") == "admin" or user.pk == getattr(
            obj, "pk", None
        )


class RolePermission(BasePermission):
    """按角色和命名权限检查访问能力。"""

    PERMISSION_ROLE_MAP = {
        "analyze_single": {"user", "admin"},
        "analyze_batch": {"user", "admin"},
        "view_analysis_history": {"user", "analyst", "admin"},
        "generate_report": {"user", "admin"},
        "view_analyst_dashboard": {"analyst", "admin"},
        "view_admin_dashboard": {"admin"},
        "manage_users": {"admin"},
        "manage_datasets": {"admin"},
        "manage_models": {"admin"},
        "manage_system_config": {"admin"},
        "view_logs": {"admin"},
    }

    @classmethod
    def get_permissions(cls, role):
        return sorted(
            permission
            for permission, roles in cls.PERMISSION_ROLE_MAP.items()
            if role in roles
        )

    @classmethod
    def has_named_permission(cls, user, permission):
        if not user or not getattr(user, "is_authenticated", False):
            return False

        allowed_roles = cls.PERMISSION_ROLE_MAP.get(permission)
        if allowed_roles is None:
            return False

        if user.role == "admin":
            return True

        return user.role in allowed_roles

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == "admin":
            return True

        required_roles = getattr(view, "required_roles", None)
        if required_roles:
            return request.user.role in required_roles

        return False

    def has_object_permission(self, request, _view, obj):
        if request.user.role == "admin":
            return True
        obj_user = getattr(obj, "user", None)
        if obj_user is None:
            return False
        return obj_user == request.user
