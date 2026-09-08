from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import TrustedDevice, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'auth_method', 'is_locked_out', 'is_staff')
    list_filter = ('auth_method', 'is_staff', 'is_superuser', 'is_active')
    # `pin` is absent from every fieldset on purpose. It holds a hash, and an
    # editable field would let a staff user paste a value straight in,
    # reintroducing the plaintext storage this replaced. Use `set_pin`.
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Estate Sentry', {
            'fields': ('auth_method', 'phone_number', 'notification_enabled'),
        }),
        ('Lockout', {
            'fields': ('failed_auth_attempts', 'locked_until'),
            'description': 'Clear these to release an account early.',
        }),
    )

    @admin.display(boolean=True, description='Locked')
    def is_locked_out(self, obj):
        return obj.is_locked_out


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'last_seen_at', 'revoked_at')
    list_filter = ('revoked_at',)
    search_fields = ('name', 'user__username')
    readonly_fields = ('id', 'token_hash', 'created_at', 'last_seen_at')

    def has_add_permission(self, request):
        # Devices are enrolled through the API, which is the only place the raw
        # token is ever produced. Adding one here could only create a device
        # nobody can authenticate with.
        return False
