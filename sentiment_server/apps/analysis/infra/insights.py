from datetime import timedelta

from django.db.models import Count, Max, Min, Q
from django.utils import timezone

CONFIDENCE_BUCKETS = (
    ("0.00-0.59", 0.00, 0.60),
    ("0.60-0.74", 0.60, 0.75),
    ("0.75-0.89", 0.75, 0.90),
    ("0.90-1.00", 0.90, 1.01),
)
DEFAULT_TREND_DAYS = 7


def _build_zero_trend_counts():
    return {"positive": 0, "neutral": 0, "negative": 0}


def _to_local_date(value):
    if not value:
        return None
    return timezone.localtime(value).date()


def _increment_trend_counts(trend_map, day, sentiment):
    if day is None:
        return
    day_key = day.isoformat()
    if day_key not in trend_map:
        return
    if sentiment == 1:
        trend_map[day_key]["positive"] += 1
    elif sentiment == -1:
        trend_map[day_key]["negative"] += 1
    else:
        trend_map[day_key]["neutral"] += 1


def _build_trend_date_skeleton(start_date, end_date):
    dates = []
    trend_map = {}
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor)
        trend_map[cursor.isoformat()] = _build_zero_trend_counts()
        cursor += timedelta(days=1)
    return dates, trend_map


def _resolve_default_trend_window(min_day, max_day):
    if not min_day and not max_day:
        fallback_end = timezone.localdate()
        return fallback_end - timedelta(days=DEFAULT_TREND_DAYS - 1), fallback_end

    resolved_start = min_day or max_day
    resolved_end = max_day or min_day
    minimum_start = resolved_end - timedelta(days=DEFAULT_TREND_DAYS - 1)
    if resolved_start > minimum_start:
        resolved_start = minimum_start
    return resolved_start, resolved_end


def _build_trend_payload(dates, trend_map):
    date_keys = [day.isoformat() for day in dates]
    return {
        "dates": date_keys,
        "series": [
            {
                "name": "积极",
                "key": "positive",
                "data": [trend_map[day_key]["positive"] for day_key in date_keys],
            },
            {
                "name": "中性",
                "key": "neutral",
                "data": [trend_map[day_key]["neutral"] for day_key in date_keys],
            },
            {
                "name": "消极",
                "key": "negative",
                "data": [trend_map[day_key]["negative"] for day_key in date_keys],
            },
        ],
        "detail": [
            {
                "date": day_key,
                "positive": trend_map[day_key]["positive"],
                "neutral": trend_map[day_key]["neutral"],
                "negative": trend_map[day_key]["negative"],
                "total": sum(trend_map[day_key].values()),
            }
            for day_key in date_keys
        ],
    }


def _resolve_visual_date_range(queryset, start_date=None, end_date=None):
    if start_date and end_date:
        return start_date, end_date

    min_day = None
    max_day = None
    for comment_time, created_at in queryset.values_list(
        "comment__comment_time",
        "created_at",
    ).iterator():
        day = _to_local_date(comment_time) or _to_local_date(created_at)
        if day is None:
            continue
        min_day = day if min_day is None or day < min_day else min_day
        max_day = day if max_day is None or day > max_day else max_day

    default_start, default_end = _resolve_default_trend_window(min_day, max_day)
    return start_date or default_start, end_date or default_end


def build_trend_payload(queryset, start_date=None, end_date=None):
    start_date, end_date = _resolve_visual_date_range(queryset, start_date, end_date)

    dates, trend_map = _build_trend_date_skeleton(start_date, end_date)

    for comment_time, created_at, sentiment in queryset.values_list(
        "comment__comment_time",
        "created_at",
        "sentiment",
    ).iterator():
        day = _to_local_date(comment_time) or _to_local_date(created_at)
        _increment_trend_counts(trend_map, day, sentiment)

    return _build_trend_payload(dates, trend_map)


def _resolve_history_date_range(queryset, start_date=None, end_date=None):
    if start_date and end_date:
        return start_date, end_date

    bounds = queryset.aggregate(
        min_created_at=Min("created_at"),
        max_created_at=Max("created_at"),
    )
    min_day = _to_local_date(bounds["min_created_at"])
    max_day = _to_local_date(bounds["max_created_at"])
    default_start, default_end = _resolve_default_trend_window(min_day, max_day)
    return start_date or default_start, end_date or default_end


def build_project_distribution(queryset, limit=8):
    rows = (
        queryset.exclude(comment__project_name__exact="")
        .values("comment__project_name")
        .annotate(count=Count("id"))
        .order_by("-count", "comment__project_name")[:limit]
    )
    return [
        {
            "label": row["comment__project_name"],
            "value": int(row["count"]),
        }
        for row in rows
    ]


def build_source_distribution(queryset, limit=8):
    rows = (
        queryset.exclude(comment__source__isnull=True)
        .exclude(comment__source__exact="")
        .values("comment__source")
        .annotate(count=Count("id"))
        .order_by("-count", "comment__source")[:limit]
    )
    return [
        {
            "label": row["comment__source"],
            "value": int(row["count"]),
        }
        for row in rows
    ]


def build_confidence_buckets(queryset):
    aggregate_kwargs = {
        f"bucket_{index}": Count(
            "id",
            filter=Q(confidence__gte=lower_bound, confidence__lt=upper_bound),
        )
        for index, (_label, lower_bound, upper_bound) in enumerate(CONFIDENCE_BUCKETS)
    }
    counts = queryset.aggregate(**aggregate_kwargs)
    return [
        {
            "label": label,
            "value": int(counts[f"bucket_{index}"] or 0),
        }
        for index, (label, _lower_bound, _upper_bound) in enumerate(CONFIDENCE_BUCKETS)
    ]


def build_priority_trend(queryset, start_date=None, end_date=None):
    start_date, end_date = _resolve_visual_date_range(queryset, start_date, end_date)
    counts_by_date = {}
    for comment_time, created_at in queryset.filter(is_priority=True).values_list(
        "comment__comment_time",
        "created_at",
    ).iterator():
        day = _to_local_date(comment_time) or _to_local_date(created_at)
        if day is not None:
            counts_by_date[day] = counts_by_date.get(day, 0) + 1

    dates = []
    counts = []
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor.isoformat())
        counts.append(counts_by_date.get(cursor, 0))
        cursor += timedelta(days=1)

    return {
        "dates": dates,
        "data": counts,
    }


def build_history_trend_payload(queryset, start_date=None, end_date=None):
    start_date, end_date = _resolve_history_date_range(queryset, start_date, end_date)

    dates, trend_map = _build_trend_date_skeleton(start_date, end_date)

    for created_at, sentiment in queryset.values_list(
        "created_at",
        "sentiment",
    ).iterator():
        _increment_trend_counts(trend_map, _to_local_date(created_at), sentiment)

    return _build_trend_payload(dates, trend_map)
