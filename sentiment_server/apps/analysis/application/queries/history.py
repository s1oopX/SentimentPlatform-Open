from collections import Counter

from django.db.models import Avg, Count, Q

from apps.analysis.api.responses import StandardResultsSetPagination
from apps.analysis.api.serializers.actions import PublicAnalysisResultSerializer
from apps.analysis.domain.keyword_rules import iter_normalized_keywords
from apps.analysis.infra.insights import (
    build_confidence_buckets,
    build_history_trend_payload,
)
from apps.analysis.infra.selectors.analysis_results import (
    apply_analysis_filters,
    build_category_distribution,
    get_analysis_result_detail_for_user,
    get_user_analysis_results_queryset,
    get_user_analysis_summary_queryset,
)


SUMMARY_SENTIMENT_KEYS = ("positive", "neutral", "negative")


def serialize_filter_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_filter_payload(validated_data):
    sentiment = validated_data.get("sentiment")
    sentiment = int(sentiment) if sentiment is not None else None
    return {
        "sentiment": sentiment,
        "start_date": serialize_filter_value(validated_data.get("start_date")),
        "end_date": serialize_filter_value(validated_data.get("end_date")),
    }


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


def build_analysis_summary_from_queryset(queryset, filters, keyword_limit):
    aggregates = queryset.aggregate(
        total=Count("id"),
        positive=Count("id", filter=Q(sentiment=1)),
        neutral=Count("id", filter=Q(sentiment=0)),
        negative=Count("id", filter=Q(sentiment=-1)),
        avg_confidence=Avg("confidence"),
    )
    total = int(aggregates["total"] or 0)
    sentiment_counts = build_sentiment_counts(
        positive=aggregates["positive"],
        neutral=aggregates["neutral"],
        negative=aggregates["negative"],
    )

    return {
        "total": total,
        "sentiment_counts": sentiment_counts,
        "sentiment_ratios": build_sentiment_ratios(sentiment_counts, total),
        "avg_confidence": round(float(aggregates["avg_confidence"] or 0), 4),
        "keyword_top": build_keyword_top(
            queryset.values_list("keywords", flat=True),
            keyword_limit=keyword_limit,
        ),
        "filters": filters,
    }


def build_history_list_payload(
    *, user, validated_data, request, paginator=None, view=None
):
    queryset = apply_analysis_filters(
        get_user_analysis_results_queryset(user),
        validated_data,
    ).order_by("-created_at", "-id")

    paginator = paginator or StandardResultsSetPagination()
    paginator.page_size = validated_data["page_size"]
    paginated_results = paginator.paginate_queryset(queryset, request, view=view)
    response = paginator.get_paginated_response(
        PublicAnalysisResultSerializer(paginated_results, many=True).data,
    )
    return response.data


def build_history_summary_payload(*, user, validated_data):
    queryset = apply_analysis_filters(
        get_user_analysis_summary_queryset(user),
        validated_data,
    )
    payload = build_analysis_summary_from_queryset(
        queryset=queryset,
        filters=build_filter_payload(validated_data),
        keyword_limit=validated_data["keyword_limit"],
    )
    if validated_data.get("include_visuals", True):
        payload.update(
            {
                "trend": build_history_trend_payload(
                    queryset,
                    validated_data.get("start_date"),
                    validated_data.get("end_date"),
                ),
                "category_distribution": build_category_distribution(queryset),
                "confidence_buckets": build_confidence_buckets(queryset),
            }
        )
    return payload


def build_history_detail_payload(*, pk=None, user=None, result=None):
    if result is None:
        result = get_analysis_result_detail_for_user(pk, user)
    if not result:
        return None
    return PublicAnalysisResultSerializer(result).data
