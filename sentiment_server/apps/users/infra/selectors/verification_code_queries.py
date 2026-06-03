from datetime import timedelta

from django.utils import timezone

from apps.users.models import EmailVerificationCode


def get_recent_unused_verification_code(email, purpose, seconds=60):
    return EmailVerificationCode.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gt=timezone.now() - timedelta(seconds=seconds),
        used=False,
    ).first()


def get_unused_verification_code_for_update(email, code_hash, purpose):
    return (
        EmailVerificationCode.objects.select_for_update()
        .filter(
            email=email,
            code=code_hash,
            purpose=purpose,
            used=False,
        )
        .first()
    )


def get_latest_verification_code_for_update(email, code_hash, purpose):
    return (
        EmailVerificationCode.objects.select_for_update()
        .filter(
            email=email,
            code=code_hash,
            purpose=purpose,
        )
        .order_by("-created_at", "-pk")
        .first()
    )


def get_pending_delivery_verification_code_by_id_for_update(
    email, verification_code_id, code_hash, purpose
):
    return (
        EmailVerificationCode.objects.select_for_update()
        .filter(
            pk=verification_code_id,
            email=email,
            code=code_hash,
            purpose=purpose,
            used=False,
            delivered_at__isnull=True,
        )
        .first()
    )


def get_latest_unused_verification_code_for_update(email, purpose):
    return (
        EmailVerificationCode.objects.select_for_update()
        .filter(
            email=email,
            purpose=purpose,
            used=False,
        )
        .first()
    )


def get_undelivered_reset_password_verification_codes():
    return EmailVerificationCode.objects.filter(
        purpose="reset_password",
        used=False,
        delivered_at__isnull=True,
        created_at__gt=timezone.now() - timedelta(minutes=5),
    ).order_by("created_at", "pk")[:50]


def delete_verification_code_by_id(verification_code_id):
    return EmailVerificationCode.objects.filter(
        pk=verification_code_id, used=False
    ).delete()


__all__ = [
    "delete_verification_code_by_id",
    "get_latest_unused_verification_code_for_update",
    "get_latest_verification_code_for_update",
    "get_pending_delivery_verification_code_by_id_for_update",
    "get_recent_unused_verification_code",
    "get_undelivered_reset_password_verification_codes",
    "get_unused_verification_code_for_update",
]
