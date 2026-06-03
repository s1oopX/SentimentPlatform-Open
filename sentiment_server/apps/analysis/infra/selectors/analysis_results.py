from collections import Counter

from django.db.models import Count, Q
from django.utils import timezone

from apps.analysis.domain.category_rules import infer_comment_category
from apps.analysis.models import AnalysisResult


def build_aware_datetime(date_value, use_end_of_day=False):
    if not date_value:
        return None

    boundary = (
        timezone.datetime.max.time() if use_end_of_day else timezone.datetime.min.time()
    )
    combined = timezone.datetime.combine(date_value, boundary)
    if timezone.is_naive(combined):
        return timezone.make_aware(combined, timezone.get_current_timezone())
    return combined


def get_user_analysis_results_queryset(user):
    return AnalysisResult.objects.filter(user=user).select_related(
        "comment"
    )


def get_user_analysis_summary_queryset(user):
    return AnalysisResult.objects.filter(user=user).select_related(
        "comment"
    )


def get_analysis_result_detail_for_user(pk, user):
    return (
        AnalysisResult.objects.select_related("comment")
        .filter(pk=pk, user=user)
        .first()
    )


def apply_analysis_filters(queryset, validated_data):
    sentiment = validated_data.get("sentiment")
    start_date = validated_data.get("start_date")
    end_date = validated_data.get("end_date")

    if sentiment is not None:
        queryset = queryset.filter(sentiment=int(sentiment))

    if start_date:
        queryset = queryset.filter(
            created_at__gte=build_aware_datetime(start_date, use_end_of_day=False)
        )

    if end_date:
        queryset = queryset.filter(
            created_at__lte=build_aware_datetime(end_date, use_end_of_day=True)
        )

    return queryset


def apply_date_range_with_comment_fallback(queryset, start_date, end_date):
    if not start_date and not end_date:
        return queryset

    comment_time_filter = Q(comment__comment_time__isnull=False)
    created_at_filter = Q(comment__comment_time__isnull=True)

    if start_date:
        start_dt = build_aware_datetime(start_date, use_end_of_day=False)
        comment_time_filter &= Q(comment__comment_time__gte=start_dt)
        created_at_filter &= Q(created_at__gte=start_dt)

    if end_date:
        end_dt = build_aware_datetime(end_date, use_end_of_day=True)
        comment_time_filter &= Q(comment__comment_time__lte=end_dt)
        created_at_filter &= Q(created_at__lte=end_dt)

    return queryset.filter(comment_time_filter | created_at_filter)


def resolve_analysis_date(result):
    if result.comment and result.comment.comment_time:
        return timezone.localtime(result.comment.comment_time).date()
    return timezone.localtime(result.created_at).date()


def build_category_distribution(queryset, limit=8):
    counter = Counter()

    for row in (
        queryset.exclude(comment__category__isnull=True)
        .exclude(comment__category__exact="")
        .values("comment__category")
        .annotate(count=Count("id"))
    ):
        counter[row["comment__category"]] += int(row["count"] or 0)

    uncategorized_filter = Q(comment__category__isnull=True) | Q(
        comment__category__exact=""
    )
    for content in queryset.filter(uncategorized_filter).values_list(
        "comment__content", flat=True
    ).iterator():
        counter[infer_comment_category(content)] += 1

    return [
        {
            "category": category,
            "count": count,
        }
        for category, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[
            :limit
        ]
    ]
