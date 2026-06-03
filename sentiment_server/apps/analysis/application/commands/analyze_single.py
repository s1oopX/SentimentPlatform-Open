from django.db import transaction

from apps.analysis.domain.category_rules import infer_comment_category
from apps.analysis.domain.keyword_rules import normalize_keywords
from apps.analysis.infra.audit_logs import write_operation_log
from apps.analysis.models import AnalysisResult, Comment


def analyze_single_comment(*, validated_data, user, client_ip=None, predict_sentiment):
    content = validated_data["content"]

    sentiment, confidence, keywords = predict_sentiment(content)
    keywords = normalize_keywords(keywords)

    with transaction.atomic():
        comment = Comment.objects.create(
            content=content,
            category=infer_comment_category(content),
        )
        analysis_result = AnalysisResult.objects.create(
            user=user,
            comment=comment,
            sentiment=sentiment,
            confidence=confidence,
            keywords=keywords,
        )

    write_operation_log(
        user=user,
        action="analyze_single",
        detail=f"单条评论分析：{content[:50]}",
        ip=client_ip,
    )
    return analysis_result
