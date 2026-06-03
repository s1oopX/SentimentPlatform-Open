import logging
import os
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from PIL import Image, UnidentifiedImageError

from apps.admin_panel.models import OperationLog
from apps.users.application.errors import UserServiceError
from apps.users.domain.password_policy import validate_user_password

logger = logging.getLogger(__name__)

_ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def generate_verification_code():
    return "".join(secrets.choice("0123456789") for _ in range(6))


def enforce_password_rules(*, password, email="", nickname="", role="user", user=None):
    try:
        validate_user_password(
            password=password,
            email=email,
            nickname=nickname,
            role=role,
            user=user,
        )
    except DjangoValidationError as exc:
        raise UserServiceError("; ".join(exc.messages), 400) from exc


def log_operation(*, user, action, detail, ip):
    try:
        OperationLog.objects.create(
            user=user,
            action=action,
            detail=detail,
            ip=ip,
        )
    except Exception:
        logger.exception(
            "users 操作日志写入失败: action=%s user_id=%s",
            action,
            getattr(user, "id", None),
        )


def validate_uploaded_avatar_file(avatar_file):
    if avatar_file is None:
        return

    # Validate file extension against allowlist to prevent polyglot uploads
    file_name = getattr(avatar_file, "name", "") or ""
    _, ext = os.path.splitext(file_name.lower())
    if ext not in _ALLOWED_AVATAR_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_AVATAR_EXTENSIONS))
        raise UserServiceError(f"头像文件格式不支持，仅允许 {allowed}", 400)

    max_upload_size = int(getattr(settings, "MAX_UPLOAD_SIZE", 0) or 0)
    if max_upload_size > 0 and avatar_file.size > max_upload_size:
        max_upload_size_mb = round(max_upload_size / (1024 * 1024), 2)
        raise UserServiceError(f"头像文件大小不能超过 {max_upload_size_mb}MB", 400)

    try:
        with Image.open(avatar_file) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise UserServiceError("请上传有效的图片文件", 400)
    finally:
        avatar_file.seek(0)


__all__ = [
    "generate_verification_code",
    "enforce_password_rules",
    "log_operation",
    "validate_uploaded_avatar_file",
]
