from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError


def logout_user(*, user, refresh_token="", client_ip=None):
    if not refresh_token:
        raise UserServiceError("缺少刷新令牌，无法完成服务端登出", 400)

    try:
        token = RefreshToken(refresh_token)
        token_user_id = token.get("user_id")
        if str(token_user_id) != str(user.id):
            raise UserServiceError("刷新令牌不属于当前用户", 403)
        token.blacklist()
    except TokenError as exc:
        raise UserServiceError("刷新令牌无效或已过期", 400) from exc

    application_shared.log_operation(
        user=user,
        action="logout",
        detail=f"用户 {user.email} 登出",
        ip=client_ip,
    )


__all__ = ["logout_user"]
