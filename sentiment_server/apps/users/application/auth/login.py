from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth.hashers import check_password as _check_password, make_password

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError
from apps.users.infra.selectors.user_queries import (
    get_user_by_email,
    get_users_by_phone,
)

# A pre-computed PBKDF2 hash used as a constant-time verifier when the queried
# user does not exist.  This prevents attackers from measuring whether
# check_password was called (and therefore whether the email is registered).
_DUMMY_ENCODED = make_password('__dummy__')


def _get_user_for_login(*, email=None, phone=None):
    email = (email or "").strip()
    phone = (phone or "").strip()

    if phone:
        users = get_users_by_phone(phone, limit=2)
        if len(users) > 1:
            raise UserServiceError("手机号关联多个账号，请使用邮箱登录", 400)
        return users[0] if users else None, phone

    if email and "@" not in email:
        users = get_users_by_phone(email, limit=2)
        if len(users) > 1:
            raise UserServiceError("手机号关联多个账号，请使用邮箱登录", 400)
        return users[0] if users else None, email

    return get_user_by_email(email), email


def login_user(*, email=None, phone=None, password, client_ip=None):
    user, login_identity = _get_user_for_login(email=email, phone=phone)
    if not user:
        # Constant-time dummy password check prevents timing-based email
        # enumeration.
        _check_password(password, _DUMMY_ENCODED)
        raise UserServiceError("账号或密码错误", 400)

    if not user.check_password(password):
        raise UserServiceError("账号或密码错误", 400)

    if user.status != 1:
        raise UserServiceError("账号已被禁用", 403)

    refresh = RefreshToken.for_user(user)

    application_shared.log_operation(
        user=user,
        action="login",
        detail=f"用户 {login_identity} 登录成功",
        ip=client_ip,
    )

    return {
        "message": "登录成功",
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "user": user,
    }


__all__ = ["login_user"]
