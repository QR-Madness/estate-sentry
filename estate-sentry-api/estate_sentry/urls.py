"""
URL configuration for estate_sentry project.
"""
from django.contrib import admin
from django.urls import include, path

from .health import health

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ahead of the app includes: the compose healthcheck polls this and it must
    # not depend on any of them resolving.
    path('api/health/', health, name='health'),
    path('api/auth/', include('authentication.urls')),
    path('api/', include('sensors.urls')),
    path('api/', include('alerts.urls')),
    path('api/', include('zones.urls')),
    path('api/intelligence/', include('intelligence.urls')),
    path('hq/', include('hq.urls')),
]

# Static files are served by WhiteNoise in every mode, ahead of URL routing — see
# MIDDLEWARE. This used to add `staticfiles_urlpatterns()` under DEBUG only,
# which meant the container, running with DEBUG off, served no static at all.
