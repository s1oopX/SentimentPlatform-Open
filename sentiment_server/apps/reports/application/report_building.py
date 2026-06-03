from django.db.models import Count, Q

from apps.admin_panel.infra.automation.system_config import get_keyword_top_k
from apps.analysis.domain.keyword_rules import iter_normalized_keywords
from apps.analysis.infra.insights import build_confidence_buckets
from apps.analysis.infra.selectors import (
    apply_analyst_filters,
    build_aware_datetime,
    build_category_distribution,
    get_visible_analyst_queryset,
)
from apps.analysis.models import AnalysisResult
from apps.reports.application.errors import ReportApplicationError
from apps.reports.domain.access_rules import resolve_live_report_role
from apps.users.application.errors import UserServiceError


def _resolve_requested_role(*, user):
    try:
        return resolve_live_report_role(user=user)
    except ReportApplicationError as exc:
        raise UserServiceError(exc.message, exc.status_code) from exc


def _apply_comment_time_or_created_at_range(
    queryset, *, start_date=None, end_date=None
):
    filters = Q()
    if start_date:
        start_boundary = build_aware_datetime(start_date, use_end_of_day=False)
        filters &= Q(comment__comment_time__gte=start_boundary) | Q(
            comment__comment_time__isnull=True, created_at__gte=start_boundary
        )
    if end_date:
        end_boundary = build_aware_datetime(end_date, use_end_of_day=True)
        filters &= Q(comment__comment_time__lte=end_boundary) | Q(
            comment__comment_time__isnull=True, created_at__lte=end_boundary
        )
    return queryset.filter(filters) if filters else queryset


def _apply_created_at_range(queryset, *, start_date=None, end_date=None):
    if start_date:
        queryset = queryset.filter(
            created_at__gte=build_aware_datetime(start_date, use_end_of_day=False)
        )
    if end_date:
        queryset = queryset.filter(
            created_at__lte=build_aware_datetime(end_date, use_end_of_day=True)
        )
    return queryset


def _get_global_report_queryset(*, start_date=None, end_date=None):
    queryset = AnalysisResult.objects.select_related("comment")
    return _apply_comment_time_or_created_at_range(
        queryset,
        start_date=start_date,
        end_date=end_date,
    )


def _get_personal_report_queryset(*, user, start_date=None, end_date=None):
    queryset = AnalysisResult.objects.filter(user=user)
    queryset = _apply_created_at_range(
        queryset,
        start_date=start_date,
        end_date=end_date,
    )
    return queryset.select_related("comment")


def build_report_queryset(*, user, request_params, start_date, end_date):
    requested_role = _resolve_requested_role(user=user)

    if requested_role == "admin":
        queryset = _get_global_report_queryset(start_date=start_date, end_date=end_date)
        category = (request_params.get("category") or "").strip()
        if category:
            queryset = queryset.filter(comment__category=category)
        return queryset

    if requested_role == "analyst":
        category = (request_params.get("category") or "").strip()
        queryset = apply_analyst_filters(
            get_visible_analyst_queryset(user),
            {
                "category": "",
                "start_date": start_date,
                "end_date": end_date,
            },
        ).select_related("comment")
        if category:
            queryset = queryset.filter(comment__category=category)
        return queryset

    return _get_personal_report_queryset(
        user=user,
        start_date=start_date,
        end_date=end_date,
    )


def build_report_summary(results):
    sentiment_totals = results.aggregate(
        total=Count("id"),
        positive=Count("id", filter=Q(sentiment=1)),
        neutral=Count("id", filter=Q(sentiment=0)),
        negative=Count("id", filter=Q(sentiment=-1)),
    )

    keyword_counter = {}
    for keywords in results.values_list("keywords", flat=True).iterator():
        for normalized in iter_normalized_keywords(keywords):
            keyword_counter[normalized] = keyword_counter.get(normalized, 0) + 1

    keyword_top = [
        {"keyword": keyword, "count": count}
        for keyword, count in sorted(
            keyword_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[: get_keyword_top_k()]
    ]

    return {
        "total": int(sentiment_totals["total"] or 0),
        "positive": int(sentiment_totals["positive"] or 0),
        "neutral": int(sentiment_totals["neutral"] or 0),
        "negative": int(sentiment_totals["negative"] or 0),
        "keyword_top": keyword_top,
        "category_distribution": build_category_distribution(results),
        "confidence_buckets": build_confidence_buckets(results),
    }


__all__ = [
    "build_report_queryset",
    "build_report_summary",
]
