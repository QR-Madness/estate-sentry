from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for custom User model."""

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Estate Sentry Settings', {
            'fields': ('auth_method', 'pin', 'phone_number', 'notification_enabled')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Estate Sentry Settings', {
            'fields': ('auth_method', 'pin', 'phone_number', 'notification_enabled')
        }),
    )

    list_display = ['username', 'email', 'first_name', 'last_name', 'auth_method', 'is_staff']
    list_filter = ['auth_method', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
