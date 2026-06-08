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
SENTIMENT_LABELS = {
    1: "积极",
    0: "中性",
    -1: "消极",
}
SENTIMENT_SUMMARY_ORDER = (
    (1, "positive", "积极"),
    (0, "neutral", "中性"),
    (-1, "negative", "消极"),
)


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


def _build_session_key(result):
    if result.analysis_session_id:
        return f"{result.analysis_channel}:{result.analysis_session_id}"
    return f"legacy:{result.pk}"


def _build_session_comment_text(session):
    representative = session["representative"]
    if session["analysis_channel"] != "batch":
        return representative.comment.content if representative.comment else ""

    source_name = session.get("analysis_source_name", "")
    source_text = f"：{source_name}" if source_name else ""
    return f"批量分析{source_text}（{session['result_count']} 条）"


def _build_sentiment_summary_text(sentiment_counts):
    return " / ".join(
        f"{label} {int(sentiment_counts.get(key, 0) or 0)}"
        for _sentiment, key, label in SENTIMENT_SUMMARY_ORDER
    )


def _build_keyword_top_from_results(results, keyword_limit=8):
    return build_keyword_top(
        [result.keywords for result in results],
        keyword_limit=keyword_limit,
    )


def _dominant_sentiment(sentiment_counts):
    if not sentiment_counts:
        return 0
    return max(
        SENTIMENT_SUMMARY_ORDER,
        key=lambda item: (int(sentiment_counts.get(item[1], 0) or 0), item[0]),
    )[0]


def _initialize_history_session(result):
    channel = result.analysis_channel or "single"
    return {
        "representative": result,
        "analysis_channel": channel,
        "analysis_channel_display": result.get_analysis_channel_display(),
        "analysis_session_id": str(result.analysis_session_id or ""),
        "analysis_source_name": result.analysis_source_name or "",
        "results": [],
        "result_count": 0,
        "sentiment_counts": build_sentiment_counts(),
        "confidence_total": 0.0,
    }


def build_history_session_payloads(queryset):
    sessions = {}
    for result in queryset:
        key = _build_session_key(result)
        if key not in sessions:
            sessions[key] = _initialize_history_session(result)

        session = sessions[key]
        session["results"].append(result)
        session["result_count"] += 1
        session["confidence_total"] += float(result.confidence)
        sentiment_key = {
            1: "positive",
            0: "neutral",
            -1: "negative",
        }.get(result.sentiment)
        if sentiment_key:
            session["sentiment_counts"][sentiment_key] += 1
        if not session["analysis_source_name"] and result.analysis_source_name:
            session["analysis_source_name"] = result.analysis_source_name

    payloads = []
    for session in sessions.values():
        representative = session["representative"]
        result_count = session["result_count"]
        sentiment_counts = session["sentiment_counts"]
        dominant_sentiment = representative.sentiment
        sentiment_display = representative.get_sentiment_display()
        if session["analysis_channel"] == "batch":
            dominant_sentiment = _dominant_sentiment(sentiment_counts)
            sentiment_display = _build_sentiment_summary_text(sentiment_counts)

        avg_confidence = (
            round(session["confidence_total"] / result_count, 4)
            if result_count
            else 0.0
        )
        sample_results = session["results"][:3]
        payloads.append(
            {
                "id": representative.pk,
                "detail_result_id": representative.pk,
                "analysis_channel": session["analysis_channel"],
                "analysis_channel_display": session["analysis_channel_display"],
                "analysis_session_id": session["analysis_session_id"],
                "analysis_source_name": session["analysis_source_name"],
                "result_count": result_count,
                "comment_content": _build_session_comment_text(session),
                "analysis_status": "completed",
                "analysis_status_display": "已完成",
                "progress": 100,
                "sentiment": dominant_sentiment,
                "sentiment_display": sentiment_display,
                "sentiment_counts": sentiment_counts,
                "confidence": avg_confidence,
                "keywords": _build_keyword_top_from_results(session["results"]),
                "sample_results": PublicAnalysisResultSerializer(
                    sample_results,
                    many=True,
                ).data,
                "created_at": representative.created_at,
            }
        )
    return payloads


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
    session_payloads = build_history_session_payloads(queryset)

    paginator = paginator or StandardResultsSetPagination()
    paginator.page_size = validated_data["page_size"]
    paginated_results = paginator.paginate_queryset(session_payloads, request, view=view)
    response = paginator.get_paginated_response(
        paginated_results,
    )
    return response.data


def _get_history_session_queryset(*, representative, user):
    if representative.analysis_channel == "batch" and representative.analysis_session_id:
        return (
            get_user_analysis_results_queryset(user)
            .filter(
                analysis_channel=representative.analysis_channel,
                analysis_session_id=representative.analysis_session_id,
            )
            .order_by("created_at", "id")
        )
    return get_user_analysis_results_queryset(user).filter(pk=representative.pk)


def build_history_session_detail_payload(*, pk, user):
    representative = get_analysis_result_detail_for_user(pk, user)
    if not representative:
        return None

    queryset = _get_history_session_queryset(
        representative=representative,
        user=user,
    )
    summary = build_analysis_summary_from_queryset(
        queryset=queryset,
        filters={},
        keyword_limit=20,
    )
    results = list(queryset)
    return {
        "id": representative.pk,
        "analysis_channel": representative.analysis_channel,
        "analysis_channel_display": representative.get_analysis_channel_display(),
        "analysis_session_id": str(representative.analysis_session_id or ""),
        "analysis_source_name": representative.analysis_source_name or "",
        "result_count": len(results),
        "summary": summary,
        "results": PublicAnalysisResultSerializer(results, many=True).data,
    }


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
