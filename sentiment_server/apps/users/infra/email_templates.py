from functools import lru_cache
from pathlib import Path

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from core.paths import find_workspace_root

WORKSPACE_ROOT = find_workspace_root(
    Path(__file__), marker_dirs=("sentiment_server", "sentiment_webapp")
)
BRAND_LOGO_PATH = (
    WORKSPACE_ROOT / "sentiment_webapp" / "public" / "brand" / "yx-logo.svg"
)


@lru_cache(maxsize=1)
def get_brand_logo_svg():
    return BRAND_LOGO_PATH.read_text(encoding="utf-8")


def build_verification_email(*, code, purpose):
    purpose_copy = {
        "register": {
            "subject": "云析智研 - 注册验证码",
            "title": "注册验证码",
            "intro": "您正在注册云析智研账号，请使用下方验证码完成邮箱验证。",
        },
        "reset_password": {
            "subject": "云析智研 - 重置密码验证码",
            "title": "重置密码验证码",
            "intro": "您正在重置云析智研账号密码，请使用下方验证码完成身份验证。",
        },
    }
    content = purpose_copy.get(purpose, purpose_copy["register"])
    context = {
        "code": code,
        "expire_minutes": 5,
        "product_name": "云析智研",
        "brand_logo_svg": mark_safe(get_brand_logo_svg()),  # noqa: S308 – SVG loaded from local static file, not user input
        **content,
    }
    return {
        "subject": content["subject"],
        "text_body": render_to_string("emails/auth_verification.txt", context),
        "html_body": render_to_string("emails/auth_verification.html", context),
    }


__all__ = ["build_verification_email", "get_brand_logo_svg"]
