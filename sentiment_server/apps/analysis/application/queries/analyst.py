from collections import Counter

from apps.analysis.domain.date_rules import resolve_overview_dates
from apps.analysis.domain.keyword_rules import iter_normalized_keywords
from apps.analysis.infra.insights import (
    build_confidence_buckets,
    build_priority_trend,
    build_project_distribution,
    build_source_distribution,
    build_trend_payload as build_insight_trend_payload,
)
from apps.analysis.infra.selectors.analysis_results import (
    build_category_distribution,
)
from apps.analysis.infra.selectors.analyst import (
    ANALYST_REVIEW_CONFIDENCE_THRESHOLD,
    apply_analyst_filters,
    get_analyst_category_options,
    get_visible_analyst_review_queryset,
    get_visible_analyst_queryset,
)


SENTIMENT_KEYS = {
    1: "positive",
    0: "neutral",
    -1: "negative",
}
SENTIMENT_DISPLAY = {
    1: "积极",
    0: "中性",
    -1: "消极",
}


def build_default_overview_dates(validated_data):
    return resolve_overview_dates(
        start_date=validated_data.get("start_date"),
        end_date=validated_data.get("end_date"),
    )


def build_sentiment_distribution_from_queryset(queryset):
    return {
        "positive": queryset.filter(sentiment=1).count(),
        "neutral": queryset.filter(sentiment=0).count(),
        "negative": queryset.filter(sentiment=-1).count(),
    }


def build_final_sentiment_distribution_from_results(results):
    distribution = {"positive": 0, "neutral": 0, "negative": 0}
    for result in results:
        key = SENTIMENT_KEYS.get(result.final_sentiment)
        if key:
            distribution[key] += 1
    return distribution


def build_correction_matrix_from_results(results):
    counter = Counter(
        (result.sentiment, result.final_sentiment)
        for result in results
        if result.final_sentiment is not None
    )
    return [
        {
            "model_sentiment": model_sentiment,
            "model_sentiment_display": SENTIMENT_DISPLAY.get(model_sentiment, ""),
            "final_sentiment": final_sentiment,
            "final_sentiment_display": SENTIMENT_DISPLAY.get(final_sentiment, ""),
            "count": count,
        }
        for (model_sentiment, final_sentiment), count in sorted(counter.items())
    ]


def build_quality_summary(queryset, *, total):
    low_confidence_count = queryset.filter(
        confidence__lt=ANALYST_REVIEW_CONFIDENCE_THRESHOLD
    ).count()
    reviewed_count = queryset.filter(reviewed_at__isnull=False).count()
    corrected_count = queryset.filter(corrected_sentiment__isnull=False).count()
    pending_review_count = queryset.filter(
        confidence__lt=ANALYST_REVIEW_CONFIDENCE_THRESHOLD,
        reviewed_at__isnull=True,
    ).count()

    def _rate(part, base):
        return round((part / base) * 100, 1) if base else 0.0

    return {
        "confidence_threshold": float(ANALYST_REVIEW_CONFIDENCE_THRESHOLD),
        "low_confidence_count": low_confidence_count,
        "low_confidence_rate": _rate(low_confidence_count, total),
        "reviewed_count": reviewed_count,
        "review_rate": _rate(reviewed_count, total),
        "corrected_count": corrected_count,
        "correction_rate": _rate(corrected_count, reviewed_count),
        "pending_review_count": pending_review_count,
    }


def build_trend_payload(queryset, start_date, end_date):
    return build_insight_trend_payload(queryset, start_date, end_date)


def build_keyword_top(keyword_lists, keyword_limit):
    counter = Counter()
    for keywords in keyword_lists:
        for normalized in iter_normalized_keywords(keywords):
            counter[normalized] += 1

    return [
        {"keyword": keyword, "count": count}
        for keyword, count in counter.most_common(keyword_limit)
    ]


def _build_range_payload(start_date, end_date):
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def _list_recent_results(queryset):
    return list(queryset.order_by("-created_at", "-id")[:8])


def build_analyst_overview_context(*, user, validated_data):
    start_date, end_date = build_default_overview_dates(validated_data)
    queryset = apply_analyst_filters(
        get_visible_analyst_queryset(user),
        {
            **validated_data,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    sentiment_distribution = build_sentiment_distribution_from_queryset(queryset)
    total = queryset.count()
    quality_summary = build_quality_summary(queryset, total=total)

    return {
        "stats": {
            "total": total,
            "positive": sentiment_distribution["positive"],
            "neutral": sentiment_distribution["neutral"],
            "negative": sentiment_distribution["negative"],
            "priority_count": queryset.filter(is_priority=True).count(),
            "pending_review_count": quality_summary["pending_review_count"],
            "reviewed_count": quality_summary["reviewed_count"],
            "low_confidence_count": quality_summary["low_confidence_count"],
        },
        "quality_summary": quality_summary,
        "sentiment_distribution": sentiment_distribution,
        "trend": build_trend_payload(queryset, start_date, end_date),
        "recent_results": _list_recent_results(queryset),
        "category_distribution": build_category_distribution(queryset),
        "project_distribution": build_project_distribution(queryset),
        "confidence_buckets": build_confidence_buckets(queryset),
        "source_distribution": build_source_distribution(queryset),
        "priority_trend": build_priority_trend(queryset, start_date, end_date),
        "keyword_top": build_keyword_top(
            queryset.values_list("keywords", flat=True),
            validated_data["keyword_limit"],
        ),
        "range": _build_range_payload(start_date, end_date),
    }


def build_analyst_comment_list_context(*, user, validated_data):
    queryset = apply_analyst_filters(
        get_visible_analyst_review_queryset(user),
        validated_data,
    ).order_by("-created_at", "-id")

    return {
        "queryset": queryset,
        "category_options": get_analyst_category_options(user),
    }


def build_analyst_report_context(*, user, validated_data):
    start_date, end_date = build_default_overview_dates(validated_data)
    queryset = apply_analyst_filters(
        get_visible_analyst_queryset(user),
        {
            **validated_data,
            "start_date": start_date,
            "end_date": end_date,
        },
    ).order_by("-created_at", "-id")

    results = list(queryset)
    result_total = len(results)
    model_sentiment_distribution = build_sentiment_distribution_from_queryset(queryset)
    final_sentiment_distribution = build_final_sentiment_distribution_from_results(results)
    trend_payload = build_trend_payload(queryset, start_date, end_date)
    detail_rows = []
    for row in trend_payload["detail"]:
        row_total = row["total"]
        detail_rows.append(
            {
                **row,
                "positive_rate": round((row["positive"] / row_total) * 100, 1)
                if row_total
                else 0.0,
            }
        )

    return {
        "summary": {
            "total": result_total,
            "positive": final_sentiment_distribution["positive"],
            "neutral": final_sentiment_distribution["neutral"],
            "negative": final_sentiment_distribution["negative"],
            "priority_count": queryset.filter(is_priority=True).count(),
        },
        "quality_summary": build_quality_summary(queryset, total=result_total),
        "sentiment_distribution": final_sentiment_distribution,
        "model_sentiment_distribution": model_sentiment_distribution,
        "final_sentiment_distribution": final_sentiment_distribution,
        "correction_matrix": build_correction_matrix_from_results(results),
        "trend": trend_payload,
        "category_distribution": build_category_distribution(queryset),
        "project_distribution": build_project_distribution(queryset),
        "confidence_buckets": build_confidence_buckets(queryset),
        "source_distribution": build_source_distribution(queryset),
        "priority_trend": build_priority_trend(queryset, start_date, end_date),
        "keyword_top": build_keyword_top(
            queryset.values_list("keywords", flat=True),
            validated_data["keyword_limit"],
        ),
        "detail_rows": detail_rows,
        "range": _build_range_payload(start_date, end_date),
    }
