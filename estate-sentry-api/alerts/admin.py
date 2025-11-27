from django.contrib import admin
from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin configuration for Alert model."""

    list_display = ['title', 'alert_type', 'severity', 'user', 'sensor', 'timestamp', 'acknowledged']
    list_filter = ['alert_type', 'severity', 'acknowledged', 'timestamp']
    search_fields = ['title', 'description', 'user__username', 'sensor__name']
    readonly_fields = ['timestamp', 'acknowledged_at']
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_type', 'severity', 'title', 'description')
        }),
        ('Related Objects', {
            'fields': ('user', 'sensor')
        }),
        ('Status', {
            'fields': ('acknowledged', 'acknowledged_at', 'acknowledged_by')
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make acknowledged_by readonly."""
        readonly = list(self.readonly_fields)
        if obj and obj.acknowledged:
            readonly.append('acknowledged_by')
        return readonly
