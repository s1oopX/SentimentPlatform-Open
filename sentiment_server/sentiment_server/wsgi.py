from django.core.wsgi import get_wsgi_application

from sentiment_server.runtime_settings import require_settings_module

require_settings_module()

application = get_wsgi_application()
