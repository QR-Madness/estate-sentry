"""
URL configuration for estate_sentry project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/', include('sensors.urls')),
    path('api/', include('alerts.urls')),
]
