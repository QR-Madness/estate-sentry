"""
URL configuration for estate_sentry project.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/', include('sensors.urls')),
    path('api/', include('alerts.urls')),
    path('api/', include('zones.urls')),
    path('api/intelligence/', include('intelligence.urls')),
    path('hq/', include('hq.urls')),
]

if settings.DEBUG:
    # `runserver` injects these itself, but the HQ streaming endpoints need an
    # ASGI server, and uvicorn does no such patching. For production the answer
    # is a static server or whitenoise, not this branch.
    urlpatterns += staticfiles_urlpatterns()
