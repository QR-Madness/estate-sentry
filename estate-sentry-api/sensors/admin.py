from django.contrib import admin
from .models import Sensor, SensorReading


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    """Admin configuration for Sensor model."""

    list_display = ['name', 'sensor_type', 'location', 'status', 'owner', 'created_at']
    list_filter = ['sensor_type', 'status', 'created_at']
    search_fields = ['name', 'location', 'owner__username']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sensor_type', 'location', 'status', 'owner')
        }),
        ('Configuration', {
            'fields': ('handler_class', 'connection_config', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    """Admin configuration for SensorReading model."""

    list_display = ['sensor', 'timestamp', 'reading_type', 'processed']
    list_filter = ['processed', 'timestamp', 'sensor__sensor_type']
    search_fields = ['sensor__name']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Reading Information', {
            'fields': ('sensor', 'value', 'reading_type', 'processed')
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
