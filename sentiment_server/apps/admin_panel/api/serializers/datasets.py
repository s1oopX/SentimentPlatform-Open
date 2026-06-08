from rest_framework import serializers

from apps.analysis.domain.review_rules import is_effectively_reviewed
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


class DatasetAnalysisResultSerializer(serializers.ModelSerializer):
    comment_id = serializers.IntegerField(source="comment.id", read_only=True)
    content = serializers.CharField(source="comment.content", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    project_name = serializers.CharField(source="comment.project_name", read_only=True)
    category = serializers.CharField(source="comment.category", read_only=True)
    source = serializers.CharField(source="comment.source", read_only=True)
    comment_time = serializers.DateTimeField(
        source="comment.comment_time", read_only=True
    )
    model_sentiment = serializers.IntegerField(source="sentiment", read_only=True)
    model_sentiment_display = serializers.CharField(
        source="get_sentiment_display", read_only=True
    )
    corrected_sentiment_display = serializers.SerializerMethodField()
    final_sentiment = serializers.SerializerMethodField()
    final_sentiment_display = serializers.SerializerMethodField()
    has_manual_correction = serializers.SerializerMethodField()
    review_status = serializers.SerializerMethodField()
    review_status_display = serializers.SerializerMethodField()
    reviewed_by_email = serializers.CharField(
        source="reviewed_by.email", read_only=True, default=""
    )
    confidence = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisResult
        fields = [
            "id",
            "comment_id",
            "content",
            "user_email",
            "project_name",
            "category",
            "source",
            "comment_time",
            "analysis_channel",
            "analysis_source_name",
            "model_sentiment",
            "model_sentiment_display",
            "corrected_sentiment",
            "corrected_sentiment_display",
            "final_sentiment",
            "final_sentiment_display",
            "has_manual_correction",
            "review_status",
            "review_status_display",
            "confidence",
            "keywords",
            "analyst_note",
            "is_priority",
            "reviewed_by_email",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_confidence(self, obj):
        return round(float(obj.confidence), 4)

    def get_corrected_sentiment_display(self, obj):
        if obj.corrected_sentiment is None:
            return ""
        return obj.get_corrected_sentiment_display()

    def get_final_sentiment(self, obj):
        return obj.final_sentiment

    def get_final_sentiment_display(self, obj):
        return obj.get_final_sentiment_display()

    def get_has_manual_correction(self, obj):
        return obj.corrected_sentiment is not None

    def get_review_status(self, obj):
        return "reviewed" if is_effectively_reviewed(obj) else "unreviewed"

    def get_review_status_display(self, obj):
        return "已审核" if is_effectively_reviewed(obj) else "未审核"


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
