import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction

import apps.users.application.shared as application_shared
from apps.users.application.errors import UserServiceError
from apps.users.default_avatar import generate_default_avatar_file
from apps.users.infra.email_templates import build_verification_email
from apps.users.domain.code_hashing import cache_verification_code_plaintext, hash_verification_code
from apps.users.models import EmailVerificationCode
from apps.users.domain.registration_roles import resolve_public_registration_role
from core.masking import mask_email

User = get_user_model()
logger = logging.getLogger(__name__)


def create_verification_code(*, email, purpose, code):
    with transaction.atomic():
        obj = EmailVerificationCode.objects.create(
            email=email, code=hash_verification_code(code), purpose=purpose
        )
        cache_verification_code_plaintext(obj.pk, code)
        return obj


def create_and_send_registration_verification_code(*, email, purpose):
    code = application_shared.generate_verification_code()
    payload = build_verification_email(code=code, purpose=purpose)
    verification_code = None

    try:
        verification_code = create_verification_code(
            email=email, purpose=purpose, code=code
        )
        message = EmailMultiAlternatives(
            payload["subject"],
            payload["text_body"],
            settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            [email],
        )
        message.attach_alternative(payload["html_body"], "text/html")
        message.send(fail_silently=False)
    except UserServiceError:
        raise
    except Exception as exc:
        if verification_code is not None:
            verification_code.delete()
        logger.exception("邮件发送失败: purpose=%s email=%s", purpose, mask_email(email))
        raise UserServiceError("邮件发送失败，请稍后重试", 500) from exc

    return True


def register_user(*, validated_data, avatar_file=None, client_ip=None):
    email = validated_data["email"]
    application_shared.validate_uploaded_avatar_file(avatar_file)
    nickname = validated_data.get("nickname") or email.split("@")[0]
    phone = validated_data.get("phone", "")
    role_present = "role" in validated_data
    raw_role = validated_data.get("role") if role_present else None
    try:
        role = resolve_public_registration_role(
            role_present=role_present, raw_role=raw_role
        )
    except ValueError as exc:
        raise UserServiceError(str(exc), 400) from exc

    application_shared.enforce_password_rules(
        password=validated_data["password"],
        email=email,
        nickname=nickname,
        role=role,
    )

    with transaction.atomic():
        verification_code = (
            EmailVerificationCode.objects.select_for_update()
            .filter(
                email=email,
                code=hash_verification_code(validated_data["code"]),
                purpose="register",
                used=False,
            )
            .first()
        )

        if not verification_code:
            raise UserServiceError("验证码无效", 400)
        if not verification_code.is_valid_code():
            raise UserServiceError("验证码已过期", 400)

        user = None
        saved_avatar_name = None

        try:
            user = User.objects.create(
                email=email,
                nickname=nickname,
                role=role,
                phone=phone,
            )
            user.set_password(validated_data["password"])
            if avatar_file is not None:
                user.avatar.save(avatar_file.name, avatar_file, save=False)
            else:
                default_avatar_file = generate_default_avatar_file(role)
                user.avatar.save(
                    default_avatar_file.name, default_avatar_file, save=False
                )
            saved_avatar_name = user.avatar.name
            user.save()
        except IntegrityError as exc:
            if user is not None and saved_avatar_name:
                user.avatar.storage.delete(saved_avatar_name)
            raise UserServiceError("该邮箱已被注册", 400) from exc
        except Exception as exc:
            if user is not None and saved_avatar_name:
                user.avatar.storage.delete(saved_avatar_name)
            raise UserServiceError("默认头像生成失败", 500) from exc

        verification_code.used = True
        verification_code.save(update_fields=["used"])

        application_shared.log_operation(
            user=user,
            action="register",
            detail=f"用户 {email} 注册成功 (角色：{role})",
            ip=client_ip,
        )

    return user


__all__ = [
    "create_and_send_registration_verification_code",
    "create_verification_code",
    "register_user",
]
