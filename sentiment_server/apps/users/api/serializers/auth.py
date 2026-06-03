from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import empty

from apps.users.captcha import verify_captcha
from apps.users.domain.password_policy import validate_user_password
from apps.users.domain.registration_roles import (
    PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR,
    resolve_public_registration_role,
)

User = get_user_model()


class PublicRegistrationRoleField(serializers.CharField):
    def run_validation(self, data=empty):
        if data is empty:
            raise serializers.ValidationError(PUBLIC_REGISTRATION_ROLE_REQUIRED_ERROR)
        return data


class SendCodeSerializer(serializers.Serializer):
    """发送验证码序列化器"""

    email = serializers.EmailField(label="邮箱", required=True)
    purpose = serializers.ChoiceField(
        label="用途",
        choices=[("register", "注册"), ("reset_password", "重置密码")],
        default="register",
        required=False,
    )

    def validate_email(self, value):
        if not value or "@" not in value:
            raise serializers.ValidationError("请输入有效的邮箱地址")
        return value


class RegisterSerializer(serializers.Serializer):
    """用户注册序列化器"""

    email = serializers.EmailField(label="邮箱", required=True)
    password = serializers.CharField(label="密码", write_only=True, required=True, max_length=128)
    password_confirm = serializers.CharField(
        label="确认密码", write_only=True, required=True, max_length=128
    )
    code = serializers.CharField(
        label="验证码", write_only=True, required=False, allow_blank=True, max_length=6
    )
    nickname = serializers.CharField(
        label="昵称", required=False, max_length=50, allow_blank=True
    )
    phone = serializers.CharField(
        label="手机号", required=False, max_length=20, allow_blank=True
    )
    role = PublicRegistrationRoleField(label="角色", required=True)

    def validate(self, attrs):
        try:
            role = resolve_public_registration_role(
                role_present="role" in attrs,
                raw_role=attrs.get("role"),
            )
        except ValueError as exc:
            raise serializers.ValidationError({"role": str(exc)}) from exc
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "两次输入的密码不一致"}
            )
        if not attrs.get("code"):
            raise serializers.ValidationError({"code": "当前注册流程需要邮箱验证码"})
        try:
            validate_user_password(
                password=attrs["password"],
                email=attrs["email"],
                nickname=attrs.get("nickname", ""),
                role=role,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        attrs["role"] = role
        return attrs

    def validate_phone(self, value):
        if value and not value.strip():
            return ""
        return value.strip() if value else ""


class CaptchaSerializer(serializers.Serializer):
    """图形验证码校验序列化器"""

    captcha_key = serializers.CharField(label="验证码键", required=True, max_length=36)
    captcha_code = serializers.CharField(label="验证码", required=True, max_length=6)

    def validate(self, attrs):
        if not verify_captcha(
            attrs.get("captcha_key", ""), attrs.get("captcha_code", "")
        ):
            raise serializers.ValidationError(
                {"captcha_code": "图形验证码错误或已过期"}
            )
        return attrs


class LoginSerializer(serializers.Serializer):
    """用户登录序列化器"""

    email = serializers.EmailField(label="邮箱", required=False, allow_blank=True)
    phone = serializers.CharField(
        label="手机号", required=False, max_length=20, allow_blank=True
    )
    password = serializers.CharField(label="密码", write_only=True, required=True, max_length=128)
    captcha_key = serializers.CharField(label="验证码键", required=True, max_length=36)
    captcha_code = serializers.CharField(label="验证码", required=True, max_length=6)

    def validate(self, attrs):
        if not verify_captcha(
            attrs.get("captcha_key", ""), attrs.get("captcha_code", "")
        ):
            raise serializers.ValidationError(
                {"captcha_code": "图形验证码错误或已过期"}
            )

        email = (attrs.get("email") or "").strip()
        phone = (attrs.get("phone") or "").strip()

        if bool(email) == bool(phone):
            raise serializers.ValidationError(
                {"non_field_errors": ["请输入邮箱或手机号二选一"]}
            )

        attrs["email"] = email
        attrs["phone"] = phone
        return attrs


class DeleteAccountSerializer(serializers.Serializer):
    """当前用户注销账号。"""

    password = serializers.CharField(label="当前密码", write_only=True, required=True, max_length=128)
    confirmation = serializers.CharField(
        label="确认文本", write_only=True, required=True, max_length=20
    )

    def validate_confirmation(self, value):
        normalized = (value or "").strip()
        if normalized != "注销账号":
            raise serializers.ValidationError("请输入“注销账号”确认操作")
        return normalized


class ChangePasswordSerializer(serializers.Serializer):
    """已登录用户修改密码"""

    old_password = serializers.CharField(
        label="当前密码", write_only=True, required=True, max_length=128
    )
    new_password = serializers.CharField(label="新密码", write_only=True, required=True, max_length=128)
    new_password_confirm = serializers.CharField(
        label="确认新密码", write_only=True, required=True, max_length=128
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "两次输入的密码不一致"}
            )
        try:
            validate_user_password(
                password=attrs["new_password"],
                user=self.context.get("user"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """重置密码序列化器"""

    email = serializers.EmailField(label="邮箱", required=True)
    code = serializers.CharField(
        label="验证码", write_only=True, required=True, max_length=6
    )
    new_password = serializers.CharField(label="新密码", write_only=True, required=True, max_length=128)
    new_password_confirm = serializers.CharField(
        label="确认新密码", write_only=True, required=True, max_length=128
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "两次输入的密码不一致"}
            )
        try:
            validate_user_password(
                password=attrs["new_password"],
                email=attrs["email"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs
