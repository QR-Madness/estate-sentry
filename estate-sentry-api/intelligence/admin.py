from django.contrib import admin

from .models import ZoneEvent


@admin.register(ZoneEvent)
class ZoneEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "zone", "camera", "object_class", "confidence")
    list_filter = ("object_class", "zone", "camera")
    date_hierarchy = "timestamp"
    readonly_fields = tuple(f.name for f in ZoneEvent._meta.fields)

    def has_add_permission(self, request):
        # Written by the pipeline, not by hand.
        return False

    def has_change_permission(self, request, obj=None):
        # An evidence log that can be edited in place is worth much less.
        return False
