import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

_PHONE_REGEX = re.compile(r'^1[3-9]\d{9}$')

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """用户信息序列化器"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "nickname",
            "display_name",
            "role",
            "role_display",
            "status",
            "status_display",
            "avatar",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "role", "status", "created_at", "updated_at"]

    def get_display_name(self, obj):
        return obj.nickname or obj.email


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """个人资料更新序列化器"""

    class Meta:
        model = User
        fields = ["phone", "nickname", "avatar"]

    def validate_phone(self, value):
        if value and not value.strip():
            return ""
        cleaned = value.strip() if value else ""
        if cleaned and not _PHONE_REGEX.match(cleaned):
            raise serializers.ValidationError("请输入有效的 11 位手机号")
        return cleaned
