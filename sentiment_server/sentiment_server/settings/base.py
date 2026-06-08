import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from core.email import resolve_email_settings
from core.paths import ensure_directories, resolve_project_path


BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def resolve_env_candidate_paths(base_dir: Path) -> list[Path]:
    candidates = [base_dir / '.env']
    parent_dir = base_dir.parent
    if parent_dir.name in {'.worktrees', 'worktrees'}:
        candidates.append(parent_dir.parent / '.env')
    return candidates


load_dotenv(BASE_DIR / '.env')
for env_path in resolve_env_candidate_paths(BASE_DIR)[1:]:
    load_dotenv(env_path)


def get_env(name: str, default=None, *, required: bool = False):
    value = os.environ.get(name)
    if value is None or value == '':
        if required:
            raise ImproperlyConfigured(f'{name} environment variable must be set')
        return default
    return value


def env_flag(name: str, default: str = 'False') -> bool:
    return get_env(name, default).lower() in ('true', 'yes', '1')


def env_list(name: str, default=None) -> list[str]:
    raw_value = get_env(name)
    if raw_value is None:
        return list(default or [])
    return [item.strip() for item in raw_value.split(',') if item.strip()]


def _safe_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        import logging

        logging.getLogger(__name__).warning(
            "Invalid integer value for %s=%r, falling back to default %d",
            name,
            raw,
            default,
        )
        return default


def env_project_path(name: str, default: str | Path, *, base_dir: Path) -> Path:
    raw_value = get_env(name, str(default))
    return resolve_project_path(raw_value, base_dir=base_dir)


def build_database_config(*, prefix: str, default_engine: str, default_name: Path | str, fallback_prefix: str | None = None):
    def resolve(name: str, default=None):
        value = os.environ.get(f'{prefix}{name}')
        if value not in (None, ''):
            return value
        if fallback_prefix:
            fallback_value = os.environ.get(f'{fallback_prefix}{name}')
            if fallback_value not in (None, ''):
                return fallback_value
        return default

    engine = resolve('ENGINE', default_engine)
    if engine != 'django.db.backends.mysql':
        raise ImproperlyConfigured(
            f'{prefix}ENGINE must be set to django.db.backends.mysql; SQLite is not supported'
        )

    database_name = resolve('NAME', str(default_name))
    if database_name in (None, ''):
        raise ImproperlyConfigured(f'{prefix}NAME environment variable must be set')

    database_user = resolve('USER')
    if database_user in (None, ''):
        raise ImproperlyConfigured(f'{prefix}USER environment variable must be set')

    database_host = resolve('HOST')
    if database_host in (None, ''):
        raise ImproperlyConfigured(f'{prefix}HOST environment variable must be set')

    database_port = resolve('PORT')
    if database_port in (None, ''):
        raise ImproperlyConfigured(f'{prefix}PORT environment variable must be set')

    return {
        'ENGINE': engine,
        'NAME': database_name,
        'USER': database_user,
        'PASSWORD': resolve('PASSWORD', ''),
        'HOST': database_host,
        'PORT': database_port,
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }


DEBUG = env_flag('DEBUG', 'False')
SECRET_KEY = get_env('SECRET_KEY', required=True)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', ['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', [])

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_SSL_REDIRECT = env_flag('SECURE_SSL_REDIRECT', 'False' if DEBUG else 'True')
SECURE_HSTS_SECONDS = _safe_int('SECURE_HSTS_SECONDS', 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'False')
SECURE_HSTS_PRELOAD = env_flag('SECURE_HSTS_PRELOAD', 'False')

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_flag('SESSION_COOKIE_SECURE', 'False' if DEBUG else 'True')

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = env_flag('CSRF_COOKIE_SECURE', 'False' if DEBUG else 'True')

ensure_directories(
    BASE_DIR / 'logs',
    BASE_DIR / 'uploads',
    BASE_DIR / 'media',
    BASE_DIR / 'staticfiles',
)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'apps.users',
    'apps.analysis',
    'apps.admin_panel',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sentiment_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sentiment_server.wsgi.application'
ASGI_APPLICATION = 'sentiment_server.asgi.application'

DATABASES = {
    'default': build_database_config(
        prefix='DB_',
        default_engine='django.db.backends.mysql',
        default_name='sentiment_analysis',
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
APPEND_SLASH = False

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.users.authentication.StatusAwareJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'URL_FORMAT_OVERRIDE': None,
    'DEFAULT_SCHEMA_CLASS': 'core.openapi.ProjectAutoSchema',
}

# Independent JWT signing key — if not set, falls back to SECRET_KEY.
# Using a separate key limits the blast radius if SECRET_KEY is compromised:
# leaked SECRET_KEY no longer allows forging JWT tokens.
JWT_SIGNING_KEY = get_env('JWT_SIGNING_KEY', required=True)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SIGNING_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'apps.users.authentication.is_active_status_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
}

JWT_REFRESH_COOKIE_NAME = 'refresh_token'
JWT_REFRESH_COOKIE_PATH = '/api/auth/'
JWT_REFRESH_COOKIE_SECURE = not DEBUG
JWT_REFRESH_COOKIE_SAMESITE = 'Lax'

AUTH_USER_MODEL = 'users.User'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

_email_settings = resolve_email_settings(os.environ)
EMAIL_BACKEND = _email_settings['EMAIL_BACKEND']
EMAIL_HOST = _email_settings['EMAIL_HOST']
EMAIL_PORT = _email_settings['EMAIL_PORT']
EMAIL_USE_SSL = _email_settings['EMAIL_USE_SSL']
EMAIL_HOST_USER = _email_settings['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = _email_settings['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = _email_settings['DEFAULT_FROM_EMAIL']

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = _safe_int('REDIS_PORT', 6379)
REDIS_DB = _safe_int('REDIS_DB', 0)
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
REDIS_SSL = env_flag('REDIS_SSL', 'False')

_redis_auth_prefix = f':{REDIS_PASSWORD}@' if REDIS_PASSWORD else ''
_redis_scheme = 'rediss' if REDIS_SSL else 'redis'
_redis_location = f'{_redis_scheme}://{_redis_auth_prefix}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', _redis_location),
    }
}

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', _redis_location)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ROUTES = {
    'apps.admin_panel.training_tasks.run_training_task': {'queue': 'training'},
    'apps.admin_panel.training_tasks.retry_training_post_run_task': {'queue': 'training'},
}

MODEL_WORKSPACE_DIR = env_project_path('MODEL_WORKSPACE_DIR', 'ml_assets', base_dir=BASE_DIR)
MODEL_PATH = env_project_path('MODEL_PATH', 'ml_assets/models/bert', base_dir=BASE_DIR)
MODEL_MAX_LENGTH = _safe_int('MODEL_MAX_LENGTH', 256)
MODEL_KEYWORD_TOP_K = _safe_int('MODEL_KEYWORD_TOP_K', 5)
MODEL_KEYWORD_MODE = os.environ.get('MODEL_KEYWORD_MODE', 'hybrid')
_VALID_KEYWORD_MODES = {'fast', 'hybrid', 'model'}
if MODEL_KEYWORD_MODE not in _VALID_KEYWORD_MODES:
    import logging
    logging.getLogger(__name__).warning(
        "Invalid MODEL_KEYWORD_MODE=%r (valid: %s), falling back to 'hybrid'",
        MODEL_KEYWORD_MODE,
        _VALID_KEYWORD_MODES,
    )
    MODEL_KEYWORD_MODE = 'hybrid'
USE_GPU = env_flag('USE_GPU', 'False')

# Restrict admin training artifact browsing to an allowlisted root directory.
# This prevents arbitrary filesystem probing via `?root=...` query params.
TRAINING_WORKSPACE_ROOT = env_project_path(
    'TRAINING_WORKSPACE_ROOT',
    str(MODEL_WORKSPACE_DIR),
    base_dir=BASE_DIR,
)
TRAINING_DATASETS_ROOT = env_project_path(
    'TRAINING_DATASETS_ROOT',
    str(MODEL_WORKSPACE_DIR / 'data'),
    base_dir=BASE_DIR,
)

UPLOAD_ROOT = BASE_DIR / 'uploads'
BACKUP_ROOT = env_project_path('BACKUP_ROOT', 'backups', base_dir=BASE_DIR)
REPORT_ROOT = env_project_path('REPORT_ROOT', 'generated_reports', base_dir=BASE_DIR)
EXPORT_ROOT = env_project_path('EXPORT_ROOT', 'exports', base_dir=BASE_DIR)
MAX_UPLOAD_SIZE = _safe_int('MAX_UPLOAD_SIZE', 10485760)
MAX_VERIFICATION_ATTEMPTS = _safe_int('MAX_VERIFICATION_ATTEMPTS', 3)
MAX_BATCH_RECORDS = _safe_int('MAX_BATCH_RECORDS', 1000)
AUTO_RETRAIN_ENABLED = env_flag('AUTO_RETRAIN_ENABLED', 'True')
AUTO_RETRAIN_MODE = get_env('AUTO_RETRAIN_MODE', 'auto')
AUTO_RETRAIN_THRESHOLD = _safe_int('AUTO_RETRAIN_THRESHOLD', 5000)
AUTO_RETRAIN_MAX_BATCHES_PER_CHECK = _safe_int('AUTO_RETRAIN_MAX_BATCHES_PER_CHECK', 3)
OPERATION_LOG_RETENTION_DAYS = _safe_int('OPERATION_LOG_RETENTION_DAYS', 180)
REPORT_PDF_TITLE = get_env('REPORT_PDF_TITLE', '情感分析报告')
REPORT_PDF_SUBTITLE = get_env('REPORT_PDF_SUBTITLE', '情感分析数据汇总')

SPECTACULAR_SETTINGS = {
    'TITLE': '云析智研 API',
    'VERSION': '0.1.0',
    'DESCRIPTION': '智能情感分析与洞察平台 - 后端 API 文档',
    'SERVE_PERMISSIONS': ['apps.users.permissions.IsAdminUserRole'],
}
SWAGGER_ENABLED = env_flag('SWAGGER_ENABLED', 'False')
