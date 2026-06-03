from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.analysis.application.queries.history import build_history_summary_payload
from apps.analysis.infra.insights import build_trend_payload
from apps.analysis.models import AnalysisResult, Comment
from apps.users.models import User


LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _aware_datetime(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=LOCAL_TZ)


def _create_result(user, *, sentiment, created_at, comment_time=None):
    comment = Comment.objects.create(
        content=f"测试评论 {sentiment} {created_at.isoformat()}",
        comment_time=comment_time,
    )
    result = AnalysisResult.objects.create(
        user=user,
        comment=comment,
        sentiment=sentiment,
        confidence=Decimal("0.9000"),
        keywords=[],
    )
    AnalysisResult.objects.filter(pk=result.pk).update(created_at=created_at)
    result.refresh_from_db()
    return result


@pytest.mark.django_db
def test_history_summary_trend_uses_result_created_at_local_dates():
    user = User.objects.create_user(
        email="history-trend@example.com",
        password="TestPass123!",
    )
    _create_result(user, sentiment=1, created_at=_aware_datetime(2026, 5, 17))
    _create_result(user, sentiment=0, created_at=_aware_datetime(2026, 5, 19))
    _create_result(user, sentiment=-1, created_at=_aware_datetime(2026, 5, 19))

    payload = build_history_summary_payload(
        user=user,
        validated_data={
            "keyword_limit": 50,
            "include_visuals": True,
        },
    )

    assert payload["sentiment_counts"] == {
        "positive": 1,
        "neutral": 1,
        "negative": 1,
    }
    assert payload["trend"]["dates"] == [
        "2026-05-13",
        "2026-05-14",
        "2026-05-15",
        "2026-05-16",
        "2026-05-17",
        "2026-05-18",
        "2026-05-19",
    ]
    assert payload["trend"]["series"] == [
        {"name": "积极", "key": "positive", "data": [0, 0, 0, 0, 1, 0, 0]},
        {"name": "中性", "key": "neutral", "data": [0, 0, 0, 0, 0, 0, 1]},
        {"name": "消极", "key": "negative", "data": [0, 0, 0, 0, 0, 0, 1]},
    ]


@pytest.mark.django_db
def test_visual_trend_prefers_comment_time_over_result_created_at():
    user = User.objects.create_user(
        email="visual-trend@example.com",
        password="TestPass123!",
    )
    result = _create_result(
        user,
        sentiment=1,
        created_at=_aware_datetime(2026, 5, 19),
        comment_time=timezone.make_aware(datetime(2026, 5, 18, 20, 30), LOCAL_TZ),
    )

    payload = build_trend_payload(AnalysisResult.objects.filter(pk=result.pk))

    assert payload["dates"] == [
        "2026-05-12",
        "2026-05-13",
        "2026-05-14",
        "2026-05-15",
        "2026-05-16",
        "2026-05-17",
        "2026-05-18",
    ]
    assert payload["series"] == [
        {"name": "积极", "key": "positive", "data": [0, 0, 0, 0, 0, 0, 1]},
        {"name": "中性", "key": "neutral", "data": [0, 0, 0, 0, 0, 0, 0]},
        {"name": "消极", "key": "negative", "data": [0, 0, 0, 0, 0, 0, 0]},
    ]
