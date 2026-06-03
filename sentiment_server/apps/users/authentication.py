from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
    default_user_authentication_rule,
)
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class StatusAwareJWTAuthentication(JWTAuthentication):
    """简化的 JWT 认证，仅检查用户状态是否启用。"""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if getattr(user, "status", 0) != 1:
            raise AuthenticationFailed("账号已被禁用", code="user_disabled")
        return user


def is_active_status_authentication_rule(user):
    """Reject disabled accounts even when an old JWT is still presented."""
    return bool(
        default_user_authentication_rule(user) and getattr(user, "status", 0) == 1
    )
