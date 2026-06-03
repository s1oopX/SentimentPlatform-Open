from datetime import timedelta

from django.conf import settings


def _refresh_max_age():
    """Return the refresh-cookie max_age in seconds, aligned to SIMPLE_JWT."""
    jwt_settings = getattr(settings, "SIMPLE_JWT", {})
    lifetime = jwt_settings.get("REFRESH_TOKEN_LIFETIME", timedelta(days=7))
    return int(lifetime.total_seconds())


def _cookie_settings():
    return {
        "name": getattr(settings, "JWT_REFRESH_COOKIE_NAME", "refresh_token"),
        "path": getattr(settings, "JWT_REFRESH_COOKIE_PATH", "/api/auth/refresh/"),
        "secure": getattr(settings, "JWT_REFRESH_COOKIE_SECURE", True),
        "samesite": getattr(settings, "JWT_REFRESH_COOKIE_SAMESITE", "Lax"),
    }


def set_refresh_token_cookie(response, refresh_token):
    cfg = _cookie_settings()
    response.set_cookie(
        key=cfg["name"],
        value=refresh_token,
        max_age=_refresh_max_age(),
        path=cfg["path"],
        secure=cfg["secure"],
        httponly=True,
        samesite=cfg["samesite"],
    )
    return response


def clear_refresh_token_cookie(response):
    cfg = _cookie_settings()
    response.delete_cookie(
        key=cfg["name"],
        path=cfg["path"],
        samesite=cfg["samesite"],
    )
    return response


def read_refresh_token_from_cookie(request):
    if request is None:
        return ""
    cfg = _cookie_settings()
    return request.COOKIES.get(cfg["name"], "") or ""
