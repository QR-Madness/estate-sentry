from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    RegisterView,
    TrustedDeviceListView,
    TrustedDeviceRevokeView,
    UserDetailView,
)

app_name = 'authentication'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('devices/', TrustedDeviceListView.as_view(), name='devices'),
    path('devices/<uuid:device_id>/revoke/', TrustedDeviceRevokeView.as_view(),
         name='device-revoke'),
]
