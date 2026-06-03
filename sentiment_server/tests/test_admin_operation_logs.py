import pytest

from apps.admin_panel.infra.selectors.logs import get_filtered_logs
from apps.admin_panel.infra.selectors.users_admin import get_filtered_users
from apps.admin_panel.models import OperationLog
from apps.users.models import User


@pytest.mark.django_db
def test_operation_log_search_matches_user_email_detail_ip_and_numeric_id():
    admin = User.objects.create_user(
        email="admin-log-search@example.com",
        password="TestPass123!",
        role="admin",
    )
    matched = OperationLog.objects.create(
        user=admin,
        action="model_switch",
        detail="切换线上模型 linear_svm",
        ip="127.0.0.9",
    )
    OperationLog.objects.create(
        user=None,
        action="login",
        detail="其他操作",
        ip="20.0.0.8",
    )

    assert list(get_filtered_logs(search="admin-log-search")) == [matched]
    assert list(get_filtered_logs(search="linear_svm")) == [matched]
    assert list(get_filtered_logs(search="127.0.0.9")) == [matched]
    assert list(get_filtered_logs(search=str(matched.pk))) == [matched]


@pytest.mark.django_db
def test_admin_user_search_matches_nickname_email_and_phone():
    matched = User.objects.create_user(
        email="search-nickname@example.com",
        password="TestPass123!",
        nickname="李晨",
        phone="13900009999",
    )
    User.objects.create_user(
        email="other-user@example.com",
        password="TestPass123!",
        nickname="王明",
        phone="13900008888",
    )

    assert list(get_filtered_users(search="李晨")) == [matched]
    assert list(get_filtered_users(search="search-nickname")) == [matched]
    assert list(get_filtered_users(search="9999")) == [matched]
