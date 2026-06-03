from django.core.asgi import get_asgi_application

from sentiment_server.runtime_settings import require_settings_module

require_settings_module()

application = get_asgi_application()
