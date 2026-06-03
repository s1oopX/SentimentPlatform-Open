from rest_framework import serializers

from apps.analysis.domain.keyword_rules import normalize_keywords
from apps.analysis.models import AnalysisResult, Comment
from apps.reports.models import Report


class CommentAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            "id",
            "content",
            "project_name",
            "score",
            "comment_time",
            "category",
            "source",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AnalysisResultAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    comment_content = serializers.CharField(source="comment.content", read_only=True)
    sentiment_display = serializers.CharField(
        source="get_sentiment_display", read_only=True
    )
    keywords = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisResult
        fields = [
            "id",
            "user",
            "user_email",
            "comment",
            "comment_content",
            "sentiment",
            "sentiment_display",
            "confidence",
            "keywords",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_keywords(self, obj):
        return normalize_keywords(obj.keywords)


class ReportAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    report_type_display = serializers.CharField(
        source="get_report_type_display", read_only=True
    )
    report_format_display = serializers.CharField(
        source="get_report_format_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "user",
            "user_email",
            "report_type",
            "report_type_display",
            "report_format",
            "report_format_display",
            "status",
            "status_display",
            "file_path",
            "file_size",
            "start_date",
            "end_date",
            "summary",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "created_at"]
