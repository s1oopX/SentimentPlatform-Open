from django.db import transaction
from django.db.models import F
from django.utils import timezone

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError
from apps.users.domain.code_hashing import delete_cached_verification_code_plaintext, hash_verification_code
from apps.users.domain.verification_rules import is_verification_code_exhausted
from apps.users.infra.selectors.user_queries import get_user_by_email
from apps.users.infra.selectors.verification_code_queries import (
    get_latest_unused_verification_code_for_update,
    get_latest_verification_code_for_update,
    get_unused_verification_code_for_update,
)
from apps.users.models import EmailVerificationCode

INVALID_RESET_CODE_ERROR = "验证码无效"


def reset_user_password(*, email, code, new_password, client_ip=None):
    error_message = None
    code_hash = hash_verification_code(code)

    with transaction.atomic():
        verification_code = get_unused_verification_code_for_update(
            email=email,
            code_hash=code_hash,
            purpose="reset_password",
        )

        if verification_code and not verification_code.is_valid_code():
            error_message = INVALID_RESET_CODE_ERROR
        elif verification_code and is_verification_code_exhausted(verification_code):
            error_message = INVALID_RESET_CODE_ERROR
        elif not verification_code:
            historical_code = get_latest_verification_code_for_update(
                email=email,
                code_hash=code_hash,
                purpose="reset_password",
            )
            active_code = get_latest_unused_verification_code_for_update(
                email=email,
                purpose="reset_password",
            )
            if (
                active_code
                and active_code.is_valid_code()
                and not is_verification_code_exhausted(active_code)
                and (not historical_code or historical_code.pk != active_code.pk)
            ):
                EmailVerificationCode.objects.filter(pk=active_code.pk).update(
                    failed_attempts=F("failed_attempts") + 1,
                    last_attempt_at=timezone.now(),
                )
            error_message = INVALID_RESET_CODE_ERROR

        if not error_message:
            user = get_user_by_email(email)
            if not user:
                error_message = INVALID_RESET_CODE_ERROR
            else:
                application_shared.enforce_password_rules(
                    password=new_password, user=user
                )
                user.set_password(new_password)
                user.save(update_fields=["password"])

                verification_code.used = True
                verification_code.save(update_fields=["used"])
                delete_cached_verification_code_plaintext(verification_code.pk)

                application_shared.log_operation(
                    user=user,
                    action="reset_password",
                    detail=f"用户 {email} 重置密码成功",
                    ip=client_ip,
                )

    if error_message:
        raise UserServiceError(error_message, 400)


__all__ = ["reset_user_password"]
