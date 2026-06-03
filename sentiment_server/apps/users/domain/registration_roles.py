PUBLIC_REGISTRATION_ROLES = {"user", "analyst"}
PUBLIC_REGISTRATION_ROLE_ERROR = "公开注册只允许创建 user 或 analyst"
PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR = "请选择注册角色"


def resolve_public_registration_role(*, role_present, raw_role):
    if not role_present:
        raise ValueError(PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR)

    if not isinstance(raw_role, str):
        raise ValueError(PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR)

    role = raw_role.strip()
    if not role:
        raise ValueError(PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR)

    if role not in PUBLIC_REGISTRATION_ROLES:
        raise ValueError(PUBLIC_REGISTRATION_ROLE_ERROR)

    return role
