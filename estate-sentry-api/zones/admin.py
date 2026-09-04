"""Zone administration.

Django admin is the zone editor for now. The specification eventually wants a
polygon drawing tool in the dashboard, but a perimeter is a short JSON array and
the admin can edit that today — which is enough to get L3 working and to find
out what the drawing tool actually needs before building one.
"""

from django.contrib import admin

from .models import Zone, ZoneAdjacency, ZonePerimeter, ZoneRule


class ZonePerimeterInline(admin.TabularInline):
    model = ZonePerimeter
    extra = 1
    fields = ("camera", "polygon")
    autocomplete_fields = ("camera",)


class ZoneRuleInline(admin.TabularInline):
    model = ZoneRule
    extra = 0
    fields = ("rule_type", "enabled", "parameters")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "zone_type", "expected_traffic", "camera_count", "owner")
    list_filter = ("zone_type", "expected_traffic")
    search_fields = ("name", "context")
    inlines = [ZonePerimeterInline, ZoneRuleInline]
    fieldsets = (
        (None, {"fields": ("name", "zone_type", "owner")}),
        (
            "Expectations",
            {
                "fields": (
                    "expected_traffic",
                    ("active_hours_start", "active_hours_end"),
                    "known_regulars",
                ),
                "description": (
                    "What normal looks like here. Leaving active hours empty means "
                    "'unknown', not 'never occupied' — the rules engine treats those "
                    "differently, so an empty schedule will not make every detection "
                    "an after-hours alert."
                ),
            },
        ),
        (
            "Context",
            {
                "fields": ("context",),
                "description": (
                    "Plain language, for the AI analysis layer. Physical detail a "
                    "model cannot infer from pixels is what earns its place here."
                ),
            },
        ),
        ("Advanced", {"fields": ("metadata",), "classes": ("collapse",)}),
    )

    @admin.display(description="Cameras")
    def camera_count(self, obj: Zone) -> int:
        return obj.perimeters.count()


@admin.register(ZonePerimeter)
class ZonePerimeterAdmin(admin.ModelAdmin):
    list_display = ("zone", "camera", "point_count")
    list_filter = ("camera",)
    autocomplete_fields = ("camera",)

    @admin.display(description="Points")
    def point_count(self, obj: ZonePerimeter) -> int:
        return len(obj.polygon or [])


@admin.register(ZoneAdjacency)
class ZoneAdjacencyAdmin(admin.ModelAdmin):
    list_display = (
        "from_zone",
        "to_zone",
        "learned_transit_seconds",
        "transit_sample_count",
        "manually_configured",
    )
    list_filter = ("manually_configured",)


@admin.register(ZoneRule)
class ZoneRuleAdmin(admin.ModelAdmin):
    list_display = ("zone", "rule_type", "enabled")
    list_filter = ("rule_type", "enabled")
