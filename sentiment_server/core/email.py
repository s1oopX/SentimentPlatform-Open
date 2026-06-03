def _to_bool(value, default=False):
    if value is None:
        return default

    return str(value).lower() in ("true", "yes", "1")


def resolve_email_settings(env):
    host = env.get("EMAIL_HOST", "smtp.qq.com")
    try:
        port = int(env.get("EMAIL_PORT", "465"))
    except (ValueError, TypeError):
        import logging

        logging.getLogger(__name__).warning(
            "Invalid EMAIL_PORT=%r, falling back to 465",
            env.get("EMAIL_PORT"),
        )
        port = 465
    use_ssl = _to_bool(env.get("EMAIL_USE_SSL", "True"), True)
    host_user = env.get("EMAIL_HOST_USER", "")
    host_password = env.get("EMAIL_HOST_PASSWORD", "")
    default_from_email = env.get("DEFAULT_FROM_EMAIL", host_user or "")

    explicit_backend = env.get("EMAIL_BACKEND")
    if explicit_backend:
        backend = explicit_backend
    elif host_user and host_password:
        backend = "django.core.mail.backends.smtp.EmailBackend"
    else:
        backend = "django.core.mail.backends.console.EmailBackend"

    return {
        "EMAIL_BACKEND": backend,
        "EMAIL_HOST": host,
        "EMAIL_PORT": port,
        "EMAIL_USE_SSL": use_ssl,
        "EMAIL_HOST_USER": host_user,
        "EMAIL_HOST_PASSWORD": host_password,
        "DEFAULT_FROM_EMAIL": default_from_email,
    }
