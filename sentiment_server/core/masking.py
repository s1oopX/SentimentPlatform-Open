"""Lightweight PII masking for log output."""


def mask_email(email):
    """Return an obfuscated email address suitable for log output.

    Example: ``user@example.com`` → ``u***@example.com``
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1) if local else "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"
