from rest_framework import serializers

from apps.analysis.api.serializers.history import (
    AnalysisHistorySerializer,
    DateRangeValidationMixin,
)
from apps.analysis.models import AnalysisResult, Model


class AnalystOverviewSerializer(DateRangeValidationMixin, serializers.Serializer):
    start_date = serializers.DateField(label="开始日期", required=False)
    end_date = serializers.DateField(label="结束日期", required=False)
    keyword_limit = serializers.IntegerField(
        label="关键词数量", default=20, min_value=1, max_value=100
    )


class AnalystCommentFilterSerializer(AnalysisHistorySerializer):
    category = serializers.CharField(label="商品类别", required=False, allow_blank=True)
    keyword = serializers.CharField(
        label="关键字搜索", required=False, allow_blank=True
    )
    is_priority = serializers.BooleanField(
        label="仅看重点评论",
        required=False,
        allow_null=True,
        default=None,
    )


class AnalystCommentNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisResult
        fields = ["analyst_note", "is_priority", "corrected_sentiment"]
        extra_kwargs = {
            "corrected_sentiment": {"required": False, "allow_null": True},
        }


class AnalystReportSerializer(DateRangeValidationMixin, serializers.Serializer):
    start_date = serializers.DateField(label="开始日期", required=False)
    end_date = serializers.DateField(label="结束日期", required=False)
    category = serializers.CharField(label="商品类别", required=False, allow_blank=True)
    keyword_limit = serializers.IntegerField(
        label="关键词数量", default=30, min_value=1, max_value=100
    )


class AnalystReportExportSerializer(AnalystReportSerializer):
    format = serializers.ChoiceField(
        label="导出格式",
        choices=[("csv", "CSV"), ("xlsx", "Excel")],
        default="xlsx",
        required=False,
    )


class ModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Model
        fields = [
            "id",
            "name",
            "version",
            "model_type",
            "metrics",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
