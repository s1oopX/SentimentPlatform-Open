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
    apply_analyst_filters,
    get_analyst_category_options,
    get_visible_analyst_queryset,
)


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

    return {
        "stats": {
            "total": queryset.count(),
            "positive": sentiment_distribution["positive"],
            "neutral": sentiment_distribution["neutral"],
            "negative": sentiment_distribution["negative"],
            "priority_count": queryset.filter(is_priority=True).count(),
        },
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
        get_visible_analyst_queryset(user),
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

    sentiment_distribution = build_sentiment_distribution_from_queryset(queryset)
    trend_payload = build_trend_payload(queryset, start_date, end_date)
    detail_rows = []
    for row in trend_payload["detail"]:
        total = row["total"]
        detail_rows.append(
            {
                **row,
                "positive_rate": round((row["positive"] / total) * 100, 1)
                if total
                else 0.0,
            }
        )

    return {
        "summary": {
            "total": queryset.count(),
            "positive": sentiment_distribution["positive"],
            "neutral": sentiment_distribution["neutral"],
            "negative": sentiment_distribution["negative"],
            "priority_count": queryset.filter(is_priority=True).count(),
        },
        "sentiment_distribution": sentiment_distribution,
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
