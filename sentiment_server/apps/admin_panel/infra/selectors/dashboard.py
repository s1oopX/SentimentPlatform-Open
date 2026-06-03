import logging
from collections import Counter
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from apps.admin_panel.models import OperationLog
from apps.analysis.domain.keyword_rules import iter_normalized_keywords
from apps.analysis.models import AnalysisResult, Comment

User = get_user_model()

ROLE_LABELS = {
    "user": "普通用户",
    "analyst": "分析师",
    "admin": "管理员",
}
SENTIMENT_KEY_MAP = {
    1: "positive",
    0: "neutral",
    -1: "negative",
}
SENTIMENT_LABEL_MAP = {
    "positive": "积极",
    "neutral": "中性",
    "negative": "消极",
}


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


def safe_percentage_change(current, previous):
    current = int(current or 0)
    previous = int(previous or 0)
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def build_sentiment_distribution(queryset):
    distribution = {"positive": 0, "neutral": 0, "negative": 0}
    aggregates = queryset.values("sentiment").annotate(count=Count("id"))
    for item in aggregates:
        key = SENTIMENT_KEY_MAP.get(item["sentiment"])
        if key:
            distribution[key] = int(item["count"])
    return distribution


def to_local_date(value):
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value).date()


def build_keyword_cloud(queryset, limit=30):
    counter = Counter()
    for keywords in queryset.values_list("keywords", flat=True).iterator():
        for normalized in iter_normalized_keywords(keywords):
            counter[normalized] += 1
    return [
        {"name": keyword, "value": count}
        for keyword, count in counter.most_common(limit)
    ]


def build_sentiment_trend(queryset, start_date, end_date):
    trend_dates = []
    current = start_date
    while current <= end_date:
        trend_dates.append(current)
        current += timedelta(days=1)

    counts_by_day = {}
    for created_at, sentiment in queryset.values_list("created_at", "sentiment").iterator():
        day = to_local_date(created_at)
        key = SENTIMENT_KEY_MAP.get(sentiment)
        if not day or not key:
            continue
        if day < start_date or day > end_date:
            continue
        counts_by_day.setdefault(day, {"positive": 0, "neutral": 0, "negative": 0})
        counts_by_day[day][key] += 1

    return {
        "dates": [day.isoformat() for day in trend_dates],
        "series": [
            {
                "name": SENTIMENT_LABEL_MAP["positive"],
                "data": [
                    counts_by_day.get(day, {}).get("positive", 0) for day in trend_dates
                ],
                "color": "#67C23A",
            },
            {
                "name": SENTIMENT_LABEL_MAP["neutral"],
                "data": [
                    counts_by_day.get(day, {}).get("neutral", 0) for day in trend_dates
                ],
                "color": "#909399",
            },
            {
                "name": SENTIMENT_LABEL_MAP["negative"],
                "data": [
                    counts_by_day.get(day, {}).get("negative", 0) for day in trend_dates
                ],
                "color": "#F56C6C",
            },
        ],
    }


def build_role_activity(start_date, end_date):
    rows = (
        OperationLog.objects.filter(
            created_at__gte=build_aware_datetime(start_date, use_end_of_day=False),
            created_at__lte=build_aware_datetime(end_date, use_end_of_day=True),
            user__isnull=False,
        )
        .values("user__role")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return [
        {
            "role": row["user__role"] or "unknown",
            "label": ROLE_LABELS.get(
                row["user__role"], row["user__role"] or "未知角色"
            ),
            "value": int(row["count"]),
        }
        for row in rows
    ]


def get_daily_average_active_users(start_at, end_at):
    users_by_day = defaultdict(set)
    rows = (
        AnalysisResult.objects.filter(created_at__gte=start_at, created_at__lte=end_at)
        .values_list("created_at", "user_id")
        .iterator()
    )
    for created_at, user_id in rows:
        day = to_local_date(created_at)
        if day is None:
            continue
        users_by_day[day].add(user_id)

    if not users_by_day:
        return 0.0
    return round(sum(len(users) for users in users_by_day.values()) / len(users_by_day), 1)


logger = logging.getLogger(__name__)

_DASHBOARD_CACHE_PREFIX = "admin:dashboard:stats"
_DASHBOARD_CACHE_TTL = 60


def build_dashboard_stats_payload(start_date, end_date):
    cache_key = f"{_DASHBOARD_CACHE_PREFIX}:{start_date.isoformat()}:{end_date.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = timezone.now()
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)
    previous_seven_days_start = seven_days_ago - timedelta(days=7)
    previous_seven_days_end = seven_days_ago - timedelta(days=1)
    yesterday = today - timedelta(days=1)

    # ── Date boundaries (reused across queries) ──────────────────────
    today_start = build_aware_datetime(today, use_end_of_day=False)
    today_end = build_aware_datetime(today, use_end_of_day=True)
    week_start = build_aware_datetime(seven_days_ago, use_end_of_day=False)
    prev_week_start = build_aware_datetime(previous_seven_days_start, use_end_of_day=False)
    prev_week_end = build_aware_datetime(previous_seven_days_end, use_end_of_day=True)
    yesterday_start = build_aware_datetime(yesterday, use_end_of_day=False)
    yesterday_end = build_aware_datetime(yesterday, use_end_of_day=True)

    # ── Query 1: AnalysisResult conditional aggregation (1 query) ───
    analysis_agg = AnalysisResult.objects.aggregate(
        total_analyses=Count("id"),
        today_analyses=Count("id", filter=Q(created_at__gte=today_start, created_at__lte=today_end)),
        yesterday_analyses=Count("id", filter=Q(created_at__gte=yesterday_start, created_at__lte=yesterday_end)),
        recent_analyses=Count("id", filter=Q(created_at__gte=week_start, created_at__lte=today_end)),
        previous_recent_analyses=Count("id", filter=Q(created_at__gte=prev_week_start, created_at__lte=prev_week_end)),
    )

    # ── Query 2: User conditional aggregation (1 query) ──────────────
    user_agg = User.objects.aggregate(
        total_users=Count("id"),
        recent_new_users=Count("id", filter=Q(created_at__gte=week_start, created_at__lte=today_end)),
        previous_recent_new_users=Count("id", filter=Q(created_at__gte=prev_week_start, created_at__lte=prev_week_end)),
    )

    # ── Query 3: Comment conditional aggregation (1 query) ──────────
    comment_agg = Comment.objects.aggregate(
        total_comments=Count("id"),
        recent_comments=Count("id", filter=Q(created_at__gte=week_start, created_at__lte=today_end)),
        previous_recent_comments=Count("id", filter=Q(created_at__gte=prev_week_start, created_at__lte=prev_week_end)),
    )

    # ── Query 4: Active users 7d (2 queries — distinct count needs subquery) ──
    active_users_7d = (
        AnalysisResult.objects.filter(created_at__gte=week_start, created_at__lte=today_end)
        .values("user_id")
        .distinct()
        .count()
    )
    previous_active_users_7d = (
        AnalysisResult.objects.filter(created_at__gte=prev_week_start, created_at__lte=prev_week_end)
        .values("user_id")
        .distinct()
        .count()
    )

    daily_avg_active_users = get_daily_average_active_users(week_start, today_end)
    prev_daily_avg = get_daily_average_active_users(prev_week_start, prev_week_end)

    # ── Range-filtered queryset for distribution/trend (lazy, evaluated by sub-functions) ──
    filtered_results = AnalysisResult.objects.filter(
        created_at__gte=build_aware_datetime(start_date, use_end_of_day=False),
        created_at__lte=build_aware_datetime(end_date, use_end_of_day=True),
    )

    payload = {
        "total_users": user_agg["total_users"],
        "total_analyses": analysis_agg["total_analyses"],
        "total_comments": comment_agg["total_comments"],
        "today_analyses": analysis_agg["today_analyses"],
        "active_users_7d": active_users_7d,
        "daily_avg_active_users": daily_avg_active_users,
        "time_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "sentiment_distribution": build_sentiment_distribution(filtered_results),
        "keyword_top": build_keyword_cloud(filtered_results),
        "sentiment_trend": build_sentiment_trend(
            filtered_results, start_date, end_date
        ),
        "role_action_frequency": build_role_activity(start_date, end_date),
        "trend_metrics": {
            "total_users": safe_percentage_change(
                user_agg["recent_new_users"], user_agg["previous_recent_new_users"]
            ),
            "total_analyses": safe_percentage_change(
                analysis_agg["recent_analyses"], analysis_agg["previous_recent_analyses"]
            ),
            "total_comments": safe_percentage_change(
                comment_agg["recent_comments"], comment_agg["previous_recent_comments"]
            ),
            "today_analyses": safe_percentage_change(
                analysis_agg["today_analyses"], analysis_agg["yesterday_analyses"]
            ),
            "active_users_7d": safe_percentage_change(
                active_users_7d, previous_active_users_7d
            ),
            "daily_avg_active_users": safe_percentage_change(
                daily_avg_active_users, prev_daily_avg
            ),
        },
        "generated_at": now.isoformat(),
    }

    cache.set(cache_key, payload, _DASHBOARD_CACHE_TTL)
    return payload
