from apps.admin_panel.application.errors import AdminPanelApplicationError


def toggle_admin_user_status_command(
    *,
    user,
    operator,
    reason,
    client_ip=None,
    create_operation_log_fn,
    error_cls=AdminPanelApplicationError,
):
    if user.id == operator.id:
        raise error_cls("不能禁用自己的账号", 400)

    user.status = 0 if user.status == 1 else 1
    user.save()
    create_operation_log_fn(
        user=operator,
        action="update_user",
        detail=f"切换用户状态：{user.email} -> {user.get_status_display()}；理由：{reason}",
        ip=client_ip,
    )
    return user


def update_admin_user_role_command(
    *,
    serializer,
    operator,
    reason,
    client_ip=None,
    create_operation_log_fn,
    error_cls=AdminPanelApplicationError,
):
    user = serializer.instance
    if user.id == operator.id:
        raise error_cls("不能修改自己的角色", 400)

    original_role = user.get_role_display()
    updated_user = serializer.save()
    create_operation_log_fn(
        user=operator,
        action="update_user",
        detail=(
            f"变更用户：{updated_user.email}；"
            f"角色：{original_role} -> {updated_user.get_role_display()}；"
            f"理由：{reason}"
        ),
        ip=client_ip,
    )
    return updated_user
