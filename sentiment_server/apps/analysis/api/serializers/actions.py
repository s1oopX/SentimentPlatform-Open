from django.conf import settings
from rest_framework import serializers

from apps.analysis.domain.keyword_rules import normalize_keywords
from apps.analysis.infra.file_parsing import BATCH_ANALYSIS_SUPPORTED_FORMATS
from apps.analysis.models import AnalysisResult, Comment


class CommentSerializer(serializers.ModelSerializer):
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


class PublicAnalysisResultSerializer(serializers.ModelSerializer):
    comment_content = serializers.CharField(source="comment.content", read_only=True)
    sentiment_display = serializers.CharField(
        source="get_sentiment_display", read_only=True
    )
    corrected_sentiment_display = serializers.SerializerMethodField()
    final_sentiment = serializers.SerializerMethodField()
    final_sentiment_display = serializers.SerializerMethodField()
    reviewed_by_email = serializers.CharField(
        source="reviewed_by.email", read_only=True, default=""
    )
    analysis_status = serializers.SerializerMethodField()
    analysis_status_display = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    confidence = serializers.SerializerMethodField()
    keywords = serializers.SerializerMethodField()
    category = serializers.CharField(source="comment.category", read_only=True)
    comment_time = serializers.DateTimeField(
        source="comment.comment_time", read_only=True
    )
    source = serializers.CharField(source="comment.source", read_only=True)
    project_name = serializers.CharField(source="comment.project_name", read_only=True)
    analysis_channel_display = serializers.CharField(
        source="get_analysis_channel_display", read_only=True
    )

    class Meta:
        model = AnalysisResult
        fields = [
            "id",
            "comment_content",
            "analysis_status",
            "analysis_status_display",
            "progress",
            "sentiment",
            "sentiment_display",
            "corrected_sentiment",
            "corrected_sentiment_display",
            "final_sentiment",
            "final_sentiment_display",
            "confidence",
            "keywords",
            "category",
            "comment_time",
            "source",
            "project_name",
            "analysis_channel",
            "analysis_channel_display",
            "analysis_session_id",
            "analysis_source_name",
            "analyst_note",
            "is_priority",
            "reviewed_by_email",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_analysis_status(self, _obj):
        return "completed"

    def get_analysis_status_display(self, _obj):
        return "已完成"

    def get_progress(self, _obj):
        return 100

    def get_confidence(self, obj):
        return round(float(obj.confidence), 4)

    def get_keywords(self, obj):
        return normalize_keywords(obj.keywords)

    def get_corrected_sentiment_display(self, obj):
        if obj.corrected_sentiment is None:
            return ""
        return obj.get_corrected_sentiment_display()

    def get_final_sentiment(self, obj):
        return obj.final_sentiment

    def get_final_sentiment_display(self, obj):
        return obj.get_final_sentiment_display()


class AnalysisResultSerializer(serializers.ModelSerializer):
    comment_content = serializers.CharField(source="comment.content", read_only=True)
    sentiment_display = serializers.CharField(
        source="get_sentiment_display", read_only=True
    )
    user_email = serializers.CharField(source="user.email", read_only=True)
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


class SingleAnalysisSerializer(serializers.Serializer):
    content = serializers.CharField(
        label="评论内容", required=True, min_length=5, max_length=1000
    )

    def validate_content(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("评论内容不能为空")
        if len(normalized) < 5:
            raise serializers.ValidationError("评论内容过短，至少需要 5 个字符")
        return normalized


class BatchAnalysisSerializer(serializers.Serializer):
    file = serializers.FileField(label="文件", required=True)

    def validate_file(self, value):
        max_upload_size = int(getattr(settings, "MAX_UPLOAD_SIZE", 0) or 0)
        if max_upload_size > 0 and value.size > max_upload_size:
            max_upload_size_mb = round(max_upload_size / (1024 * 1024), 2)
            raise serializers.ValidationError(
                f"文件大小不能超过 {max_upload_size_mb}MB"
            )

        file_name = value.name.lower()
        if not any(file_name.endswith(ext) for ext in BATCH_ANALYSIS_SUPPORTED_FORMATS):
            raise serializers.ValidationError("只支持 Excel(.xlsx) 和 TXT 格式文件")

        return value
