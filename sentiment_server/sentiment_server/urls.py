from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

_swagger_enabled = getattr(settings, 'SWAGGER_ENABLED', False)

urlpatterns = [
    path('api/healthz/', lambda request: JsonResponse({'status': 'ok'}), name='healthz'),
]

if _swagger_enabled:
    urlpatterns += [
        path('', RedirectView.as_view(url='/swagger/', permanent=False), name='root'),
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='schema-swagger-ui'),
        path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='schema-redoc'),
    ]
else:
    urlpatterns += [
        path('', RedirectView.as_view(url='/api/healthz/', permanent=False), name='root'),
    ]

urlpatterns += [
    path('api/auth/', include('apps.users.urls')),
    path('api/analyze/', include('apps.analysis.urls')),
    path('api/admin/', include('apps.admin_panel.urls')),
    path('api/report/', include('apps.reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
