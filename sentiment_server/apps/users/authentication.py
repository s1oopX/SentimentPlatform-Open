from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
    default_user_authentication_rule,
)
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password


class StatusAwareJWTAuthentication(JWTAuthentication):
    """简化的 JWT 认证，仅检查用户状态是否启用。"""

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise InvalidToken("令牌缺少用户标识") from exc

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist as exc:
            raise AuthenticationFailed(
                "账号不存在或登录状态已失效", code="user_not_found"
            ) from exc

        if getattr(user, "status", 0) != 1:
            raise AuthenticationFailed("账号已被禁用", code="user_disabled")
        if api_settings.CHECK_REVOKE_TOKEN and validated_token.get(
            api_settings.REVOKE_TOKEN_CLAIM
        ) != get_md5_hash_password(user.password):
            raise AuthenticationFailed(
                "账号密码已变更，请重新登录", code="password_changed"
            )
        return user


def is_active_status_authentication_rule(user):
    """Reject disabled accounts even when an old JWT is still presented."""
    return bool(
        default_user_authentication_rule(user) and getattr(user, "status", 0) == 1
    )
