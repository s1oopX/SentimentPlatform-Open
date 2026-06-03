import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def cleanup_expired_verification_codes_task_logic(
    *, retention_minutes=30,
):
    """删除已使用或已过期的邮箱验证码记录。"""
    from apps.users.models import EmailVerificationCode

    cutoff = timezone.now() - timedelta(minutes=retention_minutes)
    qs = EmailVerificationCode.objects.filter(
        Q(used=True) | Q(created_at__lt=cutoff)
    )
    deleted_count, _ = qs.delete()
    logger.info("已清理 %d 条过期/已用验证码", deleted_count)
    return {"deleted_count": deleted_count}
