from datetime import datetime, date

import pytest
from django.utils import timezone

from apps.admin_panel.infra.selectors.dashboard import (
    build_sentiment_trend,
    get_daily_average_active_users,
)
from apps.analysis.models import AnalysisResult, Comment
from apps.users.models import User


def _aware_datetime(year, month, day, hour=0, minute=0):
    value = datetime(year, month, day, hour, minute)
    return timezone.make_aware(value, timezone.get_current_timezone())


def _create_result(user, *, sentiment, created_at):
    comment = Comment.objects.create(content=f"dashboard comment {sentiment}")
    result = AnalysisResult.objects.create(
        user=user,
        comment=comment,
        sentiment=sentiment,
        confidence=0.9,
        keywords=[],
    )
    AnalysisResult.objects.filter(pk=result.pk).update(created_at=created_at)
    result.refresh_from_db()
    return result


@pytest.mark.django_db
def test_admin_dashboard_sentiment_trend_uses_python_local_dates():
    user = User.objects.create_user(
        email="dashboard-trend@example.com",
        password="TestPass123!",
        role="admin",
    )
    positive = _create_result(
        user,
        sentiment=1,
        created_at=_aware_datetime(2026, 5, 28, 10),
    )
    negative = _create_result(
        user,
        sentiment=-1,
        created_at=_aware_datetime(2026, 5, 28, 11),
    )

    payload = build_sentiment_trend(
        AnalysisResult.objects.filter(pk__in=[positive.pk, negative.pk]),
        date(2026, 5, 23),
        date(2026, 5, 29),
    )

    assert payload["dates"] == [
        "2026-05-23",
        "2026-05-24",
        "2026-05-25",
        "2026-05-26",
        "2026-05-27",
        "2026-05-28",
        "2026-05-29",
    ]
    assert payload["series"][0]["data"] == [0, 0, 0, 0, 0, 1, 0]
    assert payload["series"][1]["data"] == [0, 0, 0, 0, 0, 0, 0]
    assert payload["series"][2]["data"] == [0, 0, 0, 0, 0, 1, 0]


@pytest.mark.django_db
def test_admin_dashboard_daily_average_active_users_uses_local_dates():
    user_one = User.objects.create_user(
        email="dashboard-active-one@example.com",
        password="TestPass123!",
    )
    user_two = User.objects.create_user(
        email="dashboard-active-two@example.com",
        password="TestPass123!",
    )
    _create_result(user_one, sentiment=1, created_at=_aware_datetime(2026, 5, 27, 9))
    _create_result(user_two, sentiment=0, created_at=_aware_datetime(2026, 5, 27, 10))
    _create_result(user_one, sentiment=-1, created_at=_aware_datetime(2026, 5, 28, 9))

    average = get_daily_average_active_users(
        _aware_datetime(2026, 5, 23),
        _aware_datetime(2026, 5, 29, 23, 59),
    )

    assert average == 1.5
