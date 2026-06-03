from django.db import transaction
from django.utils import timezone

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError


def delete_user_account(*, user, password, confirmation, client_ip=None):
    if confirmation != "注销账号":
        raise UserServiceError('请输入"注销账号"确认操作', 400)

    if getattr(user, "role", "") == "admin":
        raise UserServiceError("管理员账号不能注销", 400)

    if not user.check_password(password):
        raise UserServiceError("当前密码错误", 400)

    original_email = user.email
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")

    with transaction.atomic():
        locked_user = user.__class__.objects.select_for_update().get(pk=user.pk)
        locked_user.email = f"deleted-{locked_user.pk}-{timestamp}@deleted.local"
        locked_user.phone = ""
        locked_user.nickname = "已注销用户"
        locked_user.status = 0
        locked_user.is_active = False
        locked_user.set_unusable_password()
        if locked_user.avatar:
            avatar_storage = locked_user.avatar.storage
            avatar_name = locked_user.avatar.name
            locked_user.avatar = None
        else:
            avatar_storage = None
            avatar_name = ""
        locked_user.save(
            update_fields=[
                "email",
                "phone",
                "nickname",
                "status",
                "is_active",
                "password",
                "avatar",
                "updated_at",
            ]
        )

    if avatar_storage and avatar_name:
        avatar_storage.delete(avatar_name)

    application_shared.log_operation(
        user=locked_user,
        action="other",
        detail=f"用户注销账号：{original_email}",
        ip=client_ip,
    )


__all__ = ["delete_user_account"]
