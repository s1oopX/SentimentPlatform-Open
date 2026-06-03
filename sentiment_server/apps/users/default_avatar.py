from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile

from apps.users.domain.registration_roles import PUBLIC_REGISTRATION_ROLES


DEFAULT_AVATAR_ASSET_DIR = (
    Path(__file__).resolve().parent / "assets" / "default_avatars"
)
DEFAULT_AVATAR_ASSET_MAP = {
    "user": DEFAULT_AVATAR_ASSET_DIR / "user.png",
    "analyst": DEFAULT_AVATAR_ASSET_DIR / "analyst.png",
}


def get_default_avatar_asset_path(role):
    if role not in PUBLIC_REGISTRATION_ROLES:
        raise RuntimeError(f"不支持的默认头像角色: {role}")

    asset_path = DEFAULT_AVATAR_ASSET_MAP[role]
    if not asset_path.exists():
        raise RuntimeError(f"默认头像资产不存在: {asset_path}")
    return asset_path


def generate_default_avatar_file(role):
    asset_path = get_default_avatar_asset_path(role)
    return ContentFile(
        asset_path.read_bytes(),
        name=f"default-avatar-{role}-{uuid4().hex[:12]}.png",
    )
