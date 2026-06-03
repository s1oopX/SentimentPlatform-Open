from .base import *
from .base import env_flag


DEBUG = env_flag('DEBUG', 'True')
SWAGGER_ENABLED = env_flag('SWAGGER_ENABLED', 'True')

# 开发环境允许匿名访问 Swagger 文档
SPECTACULAR_SETTINGS['SERVE_PERMISSIONS'] = ['rest_framework.permissions.AllowAny']  # noqa: F405

# 开发环境延长 token 有效期
from datetime import timedelta  # noqa: E402
SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] = timedelta(days=7)  # noqa: F405
SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'] = timedelta(days=30)  # noqa: F405
