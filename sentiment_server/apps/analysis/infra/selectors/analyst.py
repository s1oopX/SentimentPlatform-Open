from django.db.models import Count, Q

from apps.analysis.domain.access_rules import (
    has_analyst_access as domain_has_analyst_access,
)
from apps.analysis.models import AnalysisResult

from apps.analysis.infra.selectors.analysis_results import (
    apply_date_range_with_comment_fallback,
)


def has_analyst_access(user):
    return domain_has_analyst_access(user)


def get_analyst_base_queryset():
    return AnalysisResult.objects.select_related("comment", "user")


def get_visible_analyst_queryset(user):
    """精简后分析师可以看到所有分析结果。"""
    queryset = get_analyst_base_queryset()
    if user.role in ("admin", "analyst"):
        return queryset
    return queryset.none()


def apply_analyst_filters(queryset, validated_data):
    sentiment = validated_data.get("sentiment")
    if sentiment is not None:
        queryset = queryset.filter(sentiment=int(sentiment))

    queryset = apply_date_range_with_comment_fallback(
        queryset,
        validated_data.get("start_date"),
        validated_data.get("end_date"),
    )

    category = (validated_data.get("category") or "").strip()
    keyword = (validated_data.get("keyword") or "").strip()
    is_priority = validated_data.get("is_priority")

    if category:
        queryset = queryset.filter(comment__category__icontains=category)

    if keyword:
        queryset = queryset.filter(
            Q(comment__content__icontains=keyword)
            | Q(comment__category__icontains=keyword)
            | Q(analyst_note__icontains=keyword)
        )

    if is_priority is not None:
        queryset = queryset.filter(is_priority=is_priority)

    return queryset


def get_analyst_category_options(user):
    queryset = get_visible_analyst_queryset(user)
    return [
        row["comment__category"]
        for row in (
            queryset.exclude(comment__category__isnull=True)
            .exclude(comment__category__exact="")
            .values("comment__category")
            .annotate(count=Count("id"))
            .order_by("comment__category")
        )
    ]
