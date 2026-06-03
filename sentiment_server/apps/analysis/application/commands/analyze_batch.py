from collections import Counter

from django.db import transaction

from apps.admin_panel.infra.automation.system_config import get_max_batch_records
from apps.analysis.application.errors import AnalysisApplicationError
from apps.analysis.domain.category_rules import infer_comment_category
from apps.analysis.domain.keyword_rules import (
    iter_normalized_keywords,
    normalize_keywords,
)
from apps.analysis.infra.audit_logs import write_operation_log
from apps.analysis.infra.file_parsing import AnalysisValidationError
from apps.analysis.infra.model_runtime import ModelUnavailableError
from apps.analysis.models import AnalysisResult, Comment


SENTIMENT_KEY_MAP = {
    1: "positive",
    0: "neutral",
    -1: "negative",
}
SUMMARY_SENTIMENT_KEYS = ("positive", "neutral", "negative")


def build_keyword_top(keyword_lists, keyword_limit):
    counter = Counter()
    for keywords in keyword_lists:
        for normalized in iter_normalized_keywords(keywords):
            counter[normalized] += 1

    return [
        {"keyword": keyword, "count": count}
        for keyword, count in counter.most_common(keyword_limit)
    ]


def build_sentiment_counts(positive=0, neutral=0, negative=0):
    return {
        "positive": int(positive or 0),
        "neutral": int(neutral or 0),
        "negative": int(negative or 0),
    }


def build_sentiment_ratios(sentiment_counts, total):
    if not total:
        return {key: 0.0 for key in SUMMARY_SENTIMENT_KEYS}

    return {
        key: round(sentiment_counts[key] / total, 4) for key in SUMMARY_SENTIMENT_KEYS
    }


def build_analysis_summary_from_results(results, keyword_limit):
    sentiment_counts = build_sentiment_counts()
    confidence_total = 0.0

    for result in results:
        key = SENTIMENT_KEY_MAP.get(result.sentiment)
        if key:
            sentiment_counts[key] += 1
        confidence_total += float(result.confidence)

    total = len(results)
    avg_confidence = round(confidence_total / total, 4) if total else 0.0

    return {
        "total": total,
        "sentiment_counts": sentiment_counts,
        "sentiment_ratios": build_sentiment_ratios(sentiment_counts, total),
        "avg_confidence": avg_confidence,
        "keyword_top": build_keyword_top(
            [result.keywords for result in results],
            keyword_limit=keyword_limit,
        ),
    }


def analyze_batch_comments(
    *,
    validated_data,
    user,
    client_ip=None,
    predict_sentiment,
    parse_batch_comments,
    predict_sentiment_batch=None,
):
    uploaded_file = validated_data["file"]

    try:
        comments = parse_batch_comments(uploaded_file)
    except AnalysisValidationError as exc:
        raise AnalysisApplicationError(str(exc), 400) from exc

    if not comments:
        raise AnalysisApplicationError("文件为空或解析失败", 400)

    max_batch_records = get_max_batch_records()
    if len(comments) > max_batch_records:
        raise AnalysisApplicationError(
            f"单次分析不能超过 {max_batch_records} 条评论", 400
        )

    inference_results = []
    try:
        if predict_sentiment_batch is not None:
            batch_results = predict_sentiment_batch(comments)
            for content, (sentiment, confidence, keywords) in zip(
                comments, batch_results
            ):
                inference_results.append(
                    (content, sentiment, confidence, normalize_keywords(keywords))
                )
        else:
            for content in comments:
                sentiment, confidence, keywords = predict_sentiment(content)
                keywords = normalize_keywords(keywords)
                inference_results.append((content, sentiment, confidence, keywords))
    except ModelUnavailableError:
        raise
    except Exception as exc:
        raise AnalysisApplicationError("批量分析失败，未保存任何结果", 500) from exc

    analysis_results = []
    try:
        with transaction.atomic():
            for content, sentiment, confidence, keywords in inference_results:
                comment = Comment.objects.create(
                    content=content,
                    category=infer_comment_category(content),
                )
                analysis_results.append(
                    AnalysisResult.objects.create(
                        user=user,
                        comment=comment,
                        sentiment=sentiment,
                        confidence=confidence,
                        keywords=keywords,
                    )
                )
    except Exception as exc:
        raise AnalysisApplicationError("批量分析结果保存失败", 500) from exc

    write_operation_log(
        user=user,
        action="analyze_batch",
        detail=f"批量分析 {len(comments)} 条评论",
        ip=client_ip,
    )

    return {
        "total": len(analysis_results),
        "results": analysis_results,
        "summary": build_analysis_summary_from_results(
            analysis_results, keyword_limit=20
        ),
    }
