import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import OperationalError, InterfaceError, transaction
from django.utils import timezone

from apps.users.domain.code_hashing import (
    get_cached_verification_code_plaintext,
    hash_verification_code,
)
from apps.users.infra.email_templates import build_verification_email
from apps.users.infra.selectors.verification_code_queries import (
    delete_verification_code_by_id,
    get_pending_delivery_verification_code_by_id_for_update,
    get_undelivered_reset_password_verification_codes,
)
from apps.users.locks import verification_delivery_lock
from apps.users.models import EmailVerificationCode
from core.masking import mask_email

logger = logging.getLogger(__name__)


def _claim_pending_reset_password_delivery(*, email, verification_code_id, code):
    code_hash = hash_verification_code(code)
    with transaction.atomic():
        verification_code = get_pending_delivery_verification_code_by_id_for_update(
            email=email,
            verification_code_id=verification_code_id,
            code_hash=code_hash,
            purpose="reset_password",
        )
        if verification_code is None:
            return None
        if not verification_code.is_valid_code():
            delete_verification_code_by_id(verification_code_id)
            return None
        return verification_code


def _mark_reset_password_delivery_complete(*, email, verification_code_id, code):
    code_hash = hash_verification_code(code)
    return (
        EmailVerificationCode.objects.filter(
            pk=verification_code_id,
            email=email,
            code=code_hash,
            purpose="reset_password",
            used=False,
            delivered_at__isnull=True,
        ).update(delivered_at=timezone.now())
        == 1
    )


@shared_task(
    name="apps.users.tasks.send_reset_password_verification_email_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=60,
)
def send_reset_password_verification_email_task(*, email, verification_code_id, code):
    if verification_code_id <= 0:
        return False

    with verification_delivery_lock(
        verification_code_id=verification_code_id
    ) as acquired:
        if not acquired:
            return False

        verification_code = _claim_pending_reset_password_delivery(
            email=email,
            verification_code_id=verification_code_id,
            code=code,
        )
        if verification_code is None:
            return False

        payload = build_verification_email(code=code, purpose="reset_password")

        try:
            message = EmailMultiAlternatives(
                payload["subject"],
                payload["text_body"],
                settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                [email],
            )
            message.attach_alternative(payload["html_body"], "text/html")
            message.send(fail_silently=False)
        except Exception:
            logger.exception("重置密码验证码邮件发送失败: email=%s", mask_email(email))
            return False

        return _mark_reset_password_delivery_complete(
            email=email,
            verification_code_id=verification_code_id,
            code=code,
        )


@shared_task(
    name="apps.users.tasks.retry_undelivered_reset_password_verification_emails_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=30,
)
def retry_undelivered_reset_password_verification_emails_task():
    delivered_count = 0

    for verification_code in get_undelivered_reset_password_verification_codes():
        # verification_code.code is now a hash; retrieve plaintext from cache
        plaintext_code = get_cached_verification_code_plaintext(verification_code.pk)
        if not plaintext_code:
            # Cache expired — code is stale, mark as used and skip
            verification_code.used = True
            verification_code.save(update_fields=["used"])
            continue
        if send_reset_password_verification_email_task.run(
            email=verification_code.email,
            verification_code_id=verification_code.pk,
            code=plaintext_code,
        ):
            delivered_count += 1

    return delivered_count


__all__ = [
    "retry_undelivered_reset_password_verification_emails_task",
    "send_reset_password_verification_email_task",
]
