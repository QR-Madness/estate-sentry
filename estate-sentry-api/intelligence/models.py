"""The zone event log.

`ZoneEvent` is the "Log Everything" principle in table form: every detection
that falls inside a zone is recorded, whatever the classification says about it.
That matters because the interesting question after an incident is usually not
"what did the system alert on" but "what did it see" — and a log that only keeps
what already looked suspicious cannot answer it.

Scope: this app currently holds `ZoneEvent` only. The specification also places
`IdentityProfile`, `IdentityReviewItem` and `EntityTrack` here; those belong to
the identity and tracking phases (L4-L6) and are deliberately absent rather than
stubbed. The fields they would populate on a ZoneEvent — identity, action, track
linkage — are noted below where they will attach.
"""

from __future__ import annotations

import uuid

from django.db import models


class ZoneEvent(models.Model):
    """One detection, in one zone, at one moment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    zone = models.ForeignKey(
        "zones.Zone", on_delete=models.CASCADE, related_name="events"
    )
    camera = models.ForeignKey(
        "sensors.Sensor", on_delete=models.CASCADE, related_name="zone_events"
    )
    timestamp = models.DateTimeField(db_index=True)

    object_class = models.CharField(
        max_length=30, help_text="person, vehicle, animal, unknown"
    )
    confidence = models.FloatField()
    bounding_box = models.JSONField(
        help_text="[x1, y1, x2, y2], normalised to 0-1 like ZonePerimeter.polygon"
    )

    frame_path = models.CharField(
        max_length=500,
        help_text="Object-store key for the frame, so the event can be reviewed against the image",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Attaching later, with the phases that can populate them:
    #   identity / identity_confidence  -> L4, needs intelligence.IdentityProfile
    #   action / action_confidence      -> L5, pose estimation
    #   track_id                        -> L6, cross-frame correlation
    # Left off entirely rather than added as dead nullable columns, so the schema
    # does not imply a capability that is not there.

    class Meta:
        db_table = "zone_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["zone", "-timestamp"]),
            models.Index(fields=["object_class", "-timestamp"]),
            models.Index(fields=["camera", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.object_class} in {self.zone.name} at {self.timestamp:%Y-%m-%d %H:%M:%S}"
