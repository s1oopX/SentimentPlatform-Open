"""用户认证相关测试。"""
import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.captcha import generate_captcha, verify_captcha


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


@pytest.mark.django_db
class TestCaptcha(TestCase):
    """验证码生成与校验测试。"""

    def test_generate_returns_svg_and_key(self):
        key, svg = generate_captcha()
        assert key is not None
        assert svg.startswith('<svg')
        assert svg.endswith('</svg>')

    def test_verify_correct_code(self):
        key, _svg = generate_captcha()
        # Extract code from cache directly for testing
        from django.core.cache import cache
        code = cache.get(f'captcha:{key}')
        assert verify_captcha(key, code) is True

    def test_verify_wrong_code(self):
        key, _svg = generate_captcha()
        assert verify_captcha(key, 'WRONG') is False

    def test_verify_code_one_time_use(self):
        key, _svg = generate_captcha()
        from django.core.cache import cache
        code = cache.get(f'captcha:{key}')
        assert verify_captcha(key, code) is True
        # Second use should fail
        assert verify_captcha(key, code) is False

    def test_verify_expired_key(self):
        assert verify_captcha('nonexistent_key', 'any') is False


@pytest.mark.django_db
@NO_THROTTLE
class TestRegisterLogin(TestCase):
    """注册与登录流程测试。"""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()

    def _get_captcha_from_api(self):
        """获取图形验证码并从缓存提取明文。"""
        from django.core.cache import cache
        res = self.client.get('/api/auth/captcha/')
        key = res.data['captcha_key']
        code = cache.get(f'captcha:{key}')
        return key, code

    def _create_email_code(self, email):
        """请求邮箱验证码并从缓存提取明文。"""
        from apps.users.domain.code_hashing import get_cached_verification_code_plaintext
        from apps.users.models import EmailVerificationCode
        self.client.post('/api/auth/send-code/', {'email': email, 'purpose': 'register'})
        code_obj = EmailVerificationCode.objects.filter(email=email, purpose='register', used=False).first()
        if not code_obj:
            return ''
        return get_cached_verification_code_plaintext(code_obj.pk)

    def test_register_with_email(self):
        captcha_key, captcha_code = self._get_captcha_from_api()
        email_code = self._create_email_code('newuser@example.com')

        data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123',
            'password_confirm': 'SecurePass123',
            'nickname': 'TestUser',
            'role': 'user',
            'captcha_key': captcha_key,
            'captcha_code': captcha_code,
            'code': email_code,
        }
        res = self.client.post('/api/auth/register/', data)
        assert res.status_code == 201

    def test_login_with_email(self):
        # Register first
        captcha_key, captcha_code = self._get_captcha_from_api()
        email_code = self._create_email_code('loginuser@example.com')

        self.client.post('/api/auth/register/', {
            'email': 'loginuser@example.com',
            'password': 'SecurePass123',
            'password_confirm': 'SecurePass123',
            'nickname': 'LoginUser',
            'role': 'user',
            'captcha_key': captcha_key,
            'captcha_code': captcha_code,
            'code': email_code,
        })

        # Login (also requires captcha)
        login_captcha_key, login_captcha_code = self._get_captcha_from_api()
        login_res = self.client.post('/api/auth/login/', {
            'email': 'loginuser@example.com',
            'password': 'SecurePass123',
            'captcha_key': login_captcha_key,
            'captcha_code': login_captcha_code,
        })
        assert login_res.status_code == 200
        assert 'access_token' in login_res.data
        assert login_res.cookies.get('refresh_token') is not None

        refresh_res = self.client.post('/api/auth/refresh/', {})
        assert refresh_res.status_code == 200
        assert 'access' in refresh_res.data
        assert 'refresh' not in refresh_res.data

    def test_refresh_rejects_body_token_without_cookie(self):
        user = self._create_user_directly('body-refresh@example.com')
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = str(RefreshToken.for_user(user))
        res = self.client.post('/api/auth/refresh/', {'refresh': refresh})
        assert res.status_code == 400

    def test_logout_uses_refresh_cookie_only(self):
        self._create_user_directly('logout-cookie@example.com')
        token = self._login_direct_user('logout-cookie@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.post('/api/auth/logout/', {'refresh_token': 'body-token-is-ignored'})
        assert res.status_code == 200

    def test_logout_rejects_body_token_without_cookie(self):
        user = self._create_user_directly('logout-body@example.com')
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        token = str(refresh.access_token)
        body_refresh = str(refresh)
        self.client.cookies.clear()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.post('/api/auth/logout/', {'refresh_token': body_refresh})
        assert res.status_code == 400

    def test_delete_account_clears_refresh_cookie(self):
        self._create_user_directly('delete-cookie@example.com')
        token = self._login_direct_user('delete-cookie@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.delete('/api/auth/delete-account/', {
            'password': 'SecurePass123',
            'confirmation': '注销账号',
            'refresh_token': 'ignored-body-token',
        })

        assert res.status_code == 200
        refresh_cookie = res.cookies.get('refresh_token')
        assert refresh_cookie is not None
        assert refresh_cookie.value == ''

    def test_delete_account_rejects_admin_user(self):
        admin = self._create_user_directly('delete-admin@example.com')
        admin.role = 'admin'
        admin.save(update_fields=['role'])
        token = self._login_direct_user('delete-admin@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.delete('/api/auth/delete-account/', {
            'password': 'SecurePass123',
            'confirmation': '注销账号',
        })

        assert res.status_code == 400
        assert res.data['error'] == '管理员账号不能注销'
        admin.refresh_from_db()
        assert admin.status == 1
        assert admin.email == 'delete-admin@example.com'

    def _create_user_directly(self, email):
        from apps.users.models import User

        return User.objects.create_user(
            email=email,
            password='SecurePass123',
            nickname=email.split('@')[0],
            role='user',
        )

    def _login_direct_user(self, email):
        captcha_key, captcha_code = self._get_captcha_from_api()
        res = self.client.post('/api/auth/login/', {
            'email': email,
            'password': 'SecurePass123',
            'captcha_key': captcha_key,
            'captcha_code': captcha_code,
        })
        assert res.status_code == 200
        return res.data['access_token']

    def test_login_wrong_password(self):
        captcha_key, captcha_code = self._get_captcha_from_api()
        email_code = self._create_email_code('wrongpw@example.com')

        self.client.post('/api/auth/register/', {
            'email': 'wrongpw@example.com',
            'password': 'SecurePass123',
            'password_confirm': 'SecurePass123',
            'nickname': 'WrongPwUser',
            'role': 'user',
            'captcha_key': captcha_key,
            'captcha_code': captcha_code,
            'code': email_code,
        })

        login_captcha_key, login_captcha_code = self._get_captcha_from_api()
        login_res = self.client.post('/api/auth/login/', {
            'email': 'wrongpw@example.com',
            'password': 'WrongPassword1',
            'captcha_key': login_captcha_key,
            'captcha_code': login_captcha_code,
        })
        assert login_res.status_code in (400, 401)


@pytest.mark.django_db
class TestPasswordPolicy(TestCase):
    """密码强度校验测试。"""

    def test_validate_user_password_short(self):
        from apps.users.domain.password_policy import validate_user_password
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_user_password(password='short', email='test@example.com')

    def test_validate_user_password_numeric_only(self):
        from apps.users.domain.password_policy import validate_user_password
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_user_password(password='12345678', email='test@example.com')

    def test_validate_user_password_valid(self):
        from apps.users.domain.password_policy import validate_user_password

        # Should not raise
        validate_user_password(password='SecurePass123', email='test@example.com')
