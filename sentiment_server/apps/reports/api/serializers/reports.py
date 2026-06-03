from rest_framework import serializers

from apps.reports.application.user_messages import (
    get_user_visible_enqueue_error,
)
from apps.reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    """报告序列化器"""

    report_type_display = serializers.CharField(
        source="get_report_type_display", read_only=True
    )
    report_format_display = serializers.CharField(
        source="get_report_format_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    last_enqueue_error = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "report_type",
            "report_type_display",
            "report_format",
            "report_format_display",
            "status",
            "status_display",
            "file_size",
            "file_size_mb",
            "start_date",
            "end_date",
            "summary",
            "created_at",
            "completed_at",
            "last_enqueue_error",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "last_enqueue_error",
        ]

    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2) if obj.file_size else 0

    def get_last_enqueue_error(self, obj):
        return get_user_visible_enqueue_error(obj.last_enqueue_error)


class ReportGenerateSerializer(serializers.Serializer):
    """报告生成序列化器"""

    report_type = serializers.ChoiceField(
        label="报告类型",
        choices=[("daily", "日报"), ("weekly", "周报"), ("monthly", "月报")],
        required=True,
    )
    report_format = serializers.ChoiceField(
        label="报告格式",
        choices=[("pdf", "PDF"), ("excel", "Excel"), ("csv", "CSV")],
        default="pdf",
        required=False,
    )
    start_date = serializers.DateField(label="开始日期", required=False)
    end_date = serializers.DateField(label="结束日期", required=False)
    category = serializers.CharField(label="商品类别", required=False, allow_blank=True)

    def validate_category(self, value):
        return value.strip()

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if bool(start_date) != bool(end_date):
            raise serializers.ValidationError("开始日期和结束日期需要同时提供")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("开始日期不能晚于结束日期")

        return attrs
