"""Zones — the primary organising unit.

Cameras see pixels; people think in places. A zone is the mapping between the
two, and everything downstream (rules, alerts, threat scoring) is scoped to one.
That is why this lands before the identity and tracking work rather than after:
adding a zone foreign key to `Sensor` and `Alert` is cheap now and expensive
once there is real data to migrate.

Model shapes follow `docs/Specification.md` so the later phases fit without
rework.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Zone(models.Model):
    """A named place, with the context needed to reason about what happens in it."""

    class ZoneType(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        HALLWAY = "HALLWAY", "Hallway"
        PERIMETER = "PERIMETER", "Perimeter"
        RESTRICTED = "RESTRICTED", "Restricted"
        COMMON = "COMMON", "Common"

    class TrafficLevel(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"
        NONE = "NONE", "None"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zones"
    )
    name = models.CharField(max_length=255)
    zone_type = models.CharField(max_length=20, choices=ZoneType.choices)
    expected_traffic = models.CharField(
        max_length=10, choices=TrafficLevel.choices, default=TrafficLevel.LOW
    )

    active_hours_start = models.TimeField(
        null=True, blank=True, help_text="When this zone is normally occupied"
    )
    active_hours_end = models.TimeField(null=True, blank=True)

    known_regulars = models.JSONField(
        default=list, blank=True, help_text='Expected visitor categories, e.g. ["household", "delivery"]'
    )

    context = models.TextField(
        blank=True,
        help_text=(
            "Free-text description of the zone, in plain language. This is fed to "
            "the AI analysis layer, so physical detail that a model could not infer "
            "from pixels belongs here — for example: 'Back patio. The neighbour's "
            "cat sets off motion constantly. The gate has no lock.'"
        ),
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "zones"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_zone_type_display()})"

    def is_within_active_hours(self, when) -> bool | None:
        """Whether `when` (a time) falls inside this zone's active hours.

        Returns None when no hours are configured — "unknown", which the rules
        engine must treat differently from "outside active hours". A zone with
        no schedule should not make every detection an after-hours alert.
        """
        start, end = self.active_hours_start, self.active_hours_end
        if start is None or end is None:
            return None
        if start <= end:
            return start <= when <= end
        # A window that wraps past midnight, e.g. 22:00-06:00.
        return when >= start or when <= end


class ZonePerimeter(models.Model):
    """The polygon a zone occupies within one camera's view.

    A zone can span several cameras, so this is a separate model rather than a
    field: the front path may be visible from both the doorbell and the driveway
    camera, at different pixel coordinates in each.

    Coordinates are normalised to 0-1 rather than pixels, so a camera that
    changes resolution — or a stream served at a lower quality — does not
    silently invalidate every perimeter drawn against it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="perimeters")
    camera = models.ForeignKey(
        "sensors.Sensor",
        on_delete=models.CASCADE,
        related_name="zone_perimeters",
        limit_choices_to={"sensor_type": "CAMERA"},
    )
    polygon = models.JSONField(
        help_text="[[x1, y1], [x2, y2], ...] with each value normalised to 0-1"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "zone_perimeters"
        unique_together = ("zone", "camera")

    def __str__(self) -> str:
        return f"{self.zone.name} in {self.camera.name}"


class ZoneAdjacency(models.Model):
    """A directed edge in the zone graph: you can get from one zone to another.

    Directed on purpose. Physical space is often asymmetric — a one-way gate, a
    drop from a wall you can descend but not climb — and the transit time in one
    direction says little about the other.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="exits")
    to_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="entrances")

    learned_transit_seconds = models.FloatField(
        null=True, blank=True, help_text="Observed median transit time, learned by the pipeline"
    )
    transit_sample_count = models.IntegerField(default=0)
    manually_configured = models.BooleanField(
        default=False,
        help_text="Set when a person configured this edge; learning must not overwrite it",
    )

    class Meta:
        db_table = "zone_adjacency"
        unique_together = ("from_zone", "to_zone")
        verbose_name_plural = "zone adjacencies"

    def __str__(self) -> str:
        return f"{self.from_zone.name} -> {self.to_zone.name}"


class ZoneRule(models.Model):
    """An alert policy attached to a zone.

    Note what is *not* here: "log everything" is not a rule. It is unconditional
    behaviour of the pipeline, so it cannot be switched off by editing a row.
    That is deliberate — a security log with a configurable off switch is worth
    much less than one without.
    """

    class RuleType(models.TextChoices):
        ALERT_UNKNOWN_PERSON = "ALERT_UNKNOWN_PERSON", "Alert on unknown person"
        ALERT_AFTER_HOURS = "ALERT_AFTER_HOURS", "Alert outside active hours"
        ALERT_DWELL_TIME = "ALERT_DWELL_TIME", "Alert on dwell time"
        ALERT_ZONE_TRANSITION = "ALERT_ZONE_TRANSITION", "Alert on zone transition"
        SUPPRESS_WINDOW = "SUPPRESS_WINDOW", "Suppress alerts in a window"
        CUSTOM = "CUSTOM", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="rules")
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    enabled = models.BooleanField(default=True)
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Rule-specific, e.g. {"dwell_threshold_seconds": 30}',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "zone_rules"
        ordering = ["zone", "rule_type"]

    def __str__(self) -> str:
        state = "enabled" if self.enabled else "disabled"
        return f"{self.zone.name}: {self.get_rule_type_display()} ({state})"
