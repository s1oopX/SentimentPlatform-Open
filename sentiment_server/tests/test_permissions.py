"""权限控制相关测试。"""
import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import User


NO_THROTTLE = override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'apps.users.authentication.StatusAwareJWTAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {
            'login_identity': '1000/minute',
            'login_ip': '1000/minute',
            'send_code_identity': '1000/minute',
            'send_code_ip': '1000/minute',
            'reset_password_identity': '1000/minute',
            'reset_password_ip': '1000/minute',
            'register_identity': '1000/minute',
            'register_ip': '1000/minute',
            'captcha_ip': '1000/minute',
            'analyze_user': '1000/minute',
            'report_user': '1000/minute',
        },
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 10,
        'URL_FORMAT_OVERRIDE': None,
    }
)


def _create_user(email, role='user', password='TestPass123!'):
    user = User.objects.create_user(
        email=email,
        password=password,
        nickname=email.split('@')[0],
        role=role,
    )
    return user


def _get_auth_token(client, email, password='TestPass123!'):
    from django.core.cache import cache
    captcha_res = client.get('/api/auth/captcha/')
    captcha_key = captcha_res.data['captcha_key']
    captcha_code = cache.get(f'captcha:{captcha_key}')
    res = client.post('/api/auth/login/', {
        'email': email,
        'password': password,
        'captcha_key': captcha_key,
        'captcha_code': captcha_code,
    })
    return res.data['access_token']


@pytest.mark.django_db
@NO_THROTTLE
class TestRoleAccessControl(TestCase):
    """角色访问控制测试。"""

    def setUp(self):
        self.client = APIClient()
        self.user = _create_user('user@test.com', 'user')
        self.analyst = _create_user('analyst@test.com', 'analyst')
        self.admin = _create_user('admin@test.com', 'admin')

    def test_user_cannot_access_admin_panel(self):
        token = _get_auth_token(self.client, 'user@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/admin/users/')
        assert res.status_code == 403

    def test_analyst_cannot_access_admin_panel(self):
        token = _get_auth_token(self.client, 'analyst@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/admin/users/')
        assert res.status_code == 403

    def test_admin_can_access_admin_panel(self):
        token = _get_auth_token(self.client, 'admin@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/admin/users/')
        assert res.status_code == 200

    def test_analyst_can_access_analyst_overview(self):
        token = _get_auth_token(self.client, 'analyst@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/analyze/analyst/overview/')
        # 200 or 200 with data
        assert res.status_code in (200, 204)

    def test_user_cannot_access_analyst_overview(self):
        token = _get_auth_token(self.client, 'user@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/analyze/analyst/overview/')
        assert res.status_code == 403

    def test_unauthenticated_cannot_access_protected(self):
        res = self.client.get('/api/analyze/history/')
        assert res.status_code in (401, 403)
