import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError
from apps.users.domain.code_hashing import cache_verification_code_plaintext, delete_cached_verification_code_plaintext, hash_verification_code
from apps.users.infra.selectors.user_queries import (
    get_user_by_email_for_update,
)
from apps.users.infra.selectors.verification_code_queries import (
    get_latest_unused_verification_code_for_update,
    get_recent_unused_verification_code,
)
from apps.users.infra.tasks.reset_password_delivery import (
    send_reset_password_verification_email_task,
)
from apps.users.locks import verification_code_lock
from apps.users.models import EmailVerificationCode
from core.masking import mask_email

logger = logging.getLogger(__name__)
RESET_PASSWORD_MIN_DURATION_SECONDS = 0.25
SEND_CODE_COOLDOWN_CACHE_PREFIX = "users:send-code-cooldown"


def get_send_code_cooldown_seconds():
    return int(getattr(settings, "SEND_CODE_COOLDOWN_SECONDS", 60))


def normalize_user_identity(value):
    return (value or "").strip().casefold().replace(" ", "")


def build_send_code_cooldown_key(*, purpose, client_ip=None, email=None):
    identity = (
        normalize_user_identity(email)
        or normalize_user_identity(client_ip)
        or "anonymous"
    )
    return f"{SEND_CODE_COOLDOWN_CACHE_PREFIX}:{purpose}:{identity}"


def acquire_send_code_cooldown(*, purpose, client_ip=None, email=None):
    key = build_send_code_cooldown_key(
        purpose=purpose, client_ip=client_ip, email=email
    )
    cooldown_seconds = get_send_code_cooldown_seconds()
    if not cache.add(key, 1, cooldown_seconds):
        raise UserServiceError("请勿频繁发送验证码", 429)
    return key


def release_send_code_cooldown(cooldown_key):
    if cooldown_key:
        cache.delete(cooldown_key)


def _apply_reset_password_duration_floor(started_at):
    elapsed = time.monotonic() - started_at
    remaining = RESET_PASSWORD_MIN_DURATION_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)


def _build_reset_password_delivery_plan(*, email):
    user = get_user_by_email_for_update(email)
    active_code = get_latest_unused_verification_code_for_update(
        email=email,
        purpose="reset_password",
    )

    if not user:
        # Do NOT create any database record for non-existent emails —
        # doing so would allow timing-based email enumeration attacks.
        # Mark any stale active code as used (cleanup) and return early.
        if active_code:
            active_code.used = True
            active_code.save(update_fields=["used"])
            delete_cached_verification_code_plaintext(active_code.pk)
        return 0, None

    # Always generate a fresh code — we cannot recover the plaintext of an
    # existing code from its hash, so re-sending is impossible.  Mark any
    # active code as used first.
    if active_code:
        active_code.used = True
        active_code.save(update_fields=["used"])
        delete_cached_verification_code_plaintext(active_code.pk)

    fresh_code = application_shared.generate_verification_code()
    verification_code = EmailVerificationCode.objects.create(
        email=email,
        code=hash_verification_code(fresh_code),
        purpose="reset_password",
    )
    cache_verification_code_plaintext(verification_code.pk, fresh_code)
    return verification_code.pk, fresh_code


def prepare_reset_password_verification_delivery(*, email):
    started_at = time.monotonic()
    try:
        with verification_code_lock(email=email, purpose="reset_password") as acquired:
            if not acquired:
                raise UserServiceError("请求过于频繁，请稍后再试", 429)

            with transaction.atomic():
                return _build_reset_password_delivery_plan(email=email)
    finally:
        _apply_reset_password_duration_floor(started_at)


def enqueue_reset_password_verification_email(*, email, verification_code_id, code):
    return send_reset_password_verification_email_task.delay(
        email=email,
        verification_code_id=verification_code_id,
        code=code,
    )


def retry_reset_password_verification_email_delivery(
    *, verification_code=None, email=None, code=None
):
    target_email = verification_code.email if verification_code is not None else email
    target_verification_code_id = (
        verification_code.pk if verification_code is not None else 0
    )
    # verification_code.code is now a hash; use the explicit plaintext code
    # parameter, or fall back to the Redis cache for retry scenarios.
    from apps.users.domain.code_hashing import get_cached_verification_code_plaintext

    target_code = code
    if not target_code and verification_code is not None:
        target_code = get_cached_verification_code_plaintext(verification_code.pk)
    if not target_code:
        target_code = application_shared.generate_verification_code()

    if not target_email:
        return

    try:
        enqueue_reset_password_verification_email(
            email=target_email,
            verification_code_id=target_verification_code_id,
            code=target_code,
        )
    except Exception as exc:
        logger.exception(
            "重置密码验证码任务提交失败: email=%s verification_code_id=%s",
            mask_email(target_email),
            target_verification_code_id,
        )
        raise UserServiceError("验证码发送失败，请稍后重试", 503) from exc

    return True


def create_and_enqueue_reset_password_verification_code(*, email):
    verification_code_id, code = prepare_reset_password_verification_delivery(
        email=email
    )
    # When code is None the email does not belong to a registered user;
    # skip enqueuing the delivery task to avoid timing side-channels.
    if code is None:
        return True
    retry_reset_password_verification_email_delivery(
        verification_code=EmailVerificationCode(
            pk=verification_code_id, email=email
        ),
        code=code,
    )
    return True


def send_verification_code(*, email, purpose, client_ip=None):
    cooldown_key = None

    # NOTE: We intentionally do NOT check user_exists_with_email(email) here
    # for the "register" purpose.  Checking existence before registration would
    # leak whether an email address has an account (enumeration oracle).
    # Instead, the registration step itself will fail with a generic error when
    # the email is a duplicate.

    try:
        cooldown_key = acquire_send_code_cooldown(
            email=email,
            purpose=purpose,
            client_ip=client_ip,
        )

        if purpose == "register":
            from apps.users.application.registration.register_user import (
                create_and_send_registration_verification_code,
            )

            with verification_code_lock(email=email, purpose=purpose) as acquired:
                if not acquired:
                    raise UserServiceError("请勿频繁发送验证码", 429)

                recent_code = get_recent_unused_verification_code(
                    email=email, purpose=purpose
                )
                if recent_code:
                    raise UserServiceError("请勿频繁发送验证码", 429)

                return create_and_send_registration_verification_code(
                    email=email, purpose=purpose
                )

        recent_code = get_recent_unused_verification_code(email=email, purpose=purpose)
        if purpose != "reset_password" and recent_code:
            raise UserServiceError("请勿频繁发送验证码", 429)

        if purpose == "reset_password":
            return create_and_enqueue_reset_password_verification_code(email=email)

        from apps.users.application.registration.register_user import (
            create_and_send_registration_verification_code,
        )

        return create_and_send_registration_verification_code(
            email=email, purpose=purpose
        )
    except Exception:
        release_send_code_cooldown(cooldown_key)
        raise


__all__ = [
    "acquire_send_code_cooldown",
    "build_send_code_cooldown_key",
    "create_and_enqueue_reset_password_verification_code",
    "enqueue_reset_password_verification_email",
    "prepare_reset_password_verification_delivery",
    "release_send_code_cooldown",
    "retry_reset_password_verification_email_delivery",
    "send_verification_code",
]
