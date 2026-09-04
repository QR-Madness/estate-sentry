"""Zone event serialization.

The write path is used by the perception service, which posts one event per
detection that lands inside a zone.
"""

from rest_framework import serializers

from .models import ZoneEvent


class ZoneEventSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = ZoneEvent
        fields = [
            "id", "zone", "zone_name", "camera", "camera_name", "timestamp",
            "object_class", "confidence", "bounding_box", "frame_path",
            "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ZoneEventBulkSerializer(serializers.Serializer):
    """Accepts a batch of events in one request.

    The pipeline produces several detections per frame, and at a few frames per
    second per camera a request each would spend more time on HTTP round trips
    than on inference.
    """

    events = ZoneEventSerializer(many=True)

    def create(self, validated_data):
        events = [ZoneEvent(**item) for item in validated_data["events"]]
        return {"events": ZoneEvent.objects.bulk_create(events)}
