"""Zone serializers.

`ZoneSerializer` doubles as the perception service's view of a zone: it fetches
these on startup and caches them, so the fields here are the ones L3 needs to do
point-in-polygon work, not just what a human wants to see.
"""

from rest_framework import serializers

from .models import Zone, ZoneAdjacency, ZonePerimeter, ZoneRule


class ZonePerimeterSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = ZonePerimeter
        fields = ["id", "zone", "camera", "camera_name", "polygon", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_polygon(self, value):
        """A malformed perimeter silently stops matching anything, which looks
        like a quiet pipeline rather than a bad shape. Reject it at the door."""
        if not isinstance(value, list) or len(value) < 3:
            raise serializers.ValidationError("A polygon needs at least three points.")
        for point in value:
            if not (isinstance(point, (list, tuple)) and len(point) == 2):
                raise serializers.ValidationError("Each point must be [x, y].")
            x, y = point
            if not all(isinstance(c, (int, float)) for c in (x, y)):
                raise serializers.ValidationError("Coordinates must be numbers.")
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise serializers.ValidationError(
                    "Coordinates are normalised to 0-1, not pixels."
                )
        return value


class ZoneRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZoneRule
        fields = ["id", "zone", "rule_type", "enabled", "parameters", "created_at"]
        read_only_fields = ["id", "created_at"]


class ZoneAdjacencySerializer(serializers.ModelSerializer):
    from_zone_name = serializers.CharField(source="from_zone.name", read_only=True)
    to_zone_name = serializers.CharField(source="to_zone.name", read_only=True)

    class Meta:
        model = ZoneAdjacency
        fields = [
            "id", "from_zone", "from_zone_name", "to_zone", "to_zone_name",
            "learned_transit_seconds", "transit_sample_count", "manually_configured",
        ]
        read_only_fields = ["id"]


class ZoneSerializer(serializers.ModelSerializer):
    perimeters = ZonePerimeterSerializer(many=True, read_only=True)
    rules = ZoneRuleSerializer(many=True, read_only=True)
    zone_type_display = serializers.CharField(source="get_zone_type_display", read_only=True)

    class Meta:
        model = Zone
        fields = [
            "id", "name", "zone_type", "zone_type_display", "expected_traffic",
            "active_hours_start", "active_hours_end", "known_regulars", "context",
            "metadata", "owner", "perimeters", "rules", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)
