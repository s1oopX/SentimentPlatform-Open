from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.admin_panel.models import OperationLog

User = get_user_model()


class OperationLogSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = OperationLog
        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "action_display",
            "detail",
            "ip",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


class UserAdminSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
            "last_login",
        ]
        read_only_fields = ["id", "email", "status", "created_at", "updated_at", "last_login"]

    def get_display_name(self, obj):
        return obj.nickname or obj.email

    def validate(self, attrs):
        if "role" in attrs and attrs["role"] not in {"user", "analyst"}:
            raise serializers.ValidationError(
                {"role": "后台用户管理只允许设置为 user 或 analyst"}
            )
        if self.instance and getattr(self.instance, "role", None) == "admin" and "role" in attrs:
            raise serializers.ValidationError(
                {"role": "无法修改管理员角色"}
            )
        return attrs

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
