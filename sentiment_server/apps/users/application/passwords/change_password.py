import logging

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError

logger = logging.getLogger(__name__)


def change_user_password(*, user, old_password, new_password, client_ip=None):
    if not user.check_password(old_password):
        raise UserServiceError("当前密码错误", 400)

    application_shared.enforce_password_rules(password=new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])

    application_shared.log_operation(
        user=user,
        action="change_password",
        detail=f"用户 {user.email} 修改密码成功",
        ip=client_ip,
    )


__all__ = ["change_user_password"]
