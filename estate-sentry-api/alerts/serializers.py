from rest_framework import serializers
from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model."""

    sensor_name = serializers.CharField(source='sensor.name', read_only=True, allow_null=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    acknowledged_by_username = serializers.CharField(
        source='acknowledged_by.username',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type', 'alert_type_display', 'severity', 'severity_display',
            'sensor', 'sensor_name', 'user', 'timestamp', 'title', 'description',
            'acknowledged', 'acknowledged_at', 'acknowledged_by',
            'acknowledged_by_username', 'metadata'
        ]
        read_only_fields = [
            'id', 'user', 'timestamp', 'acknowledged_at', 'acknowledged_by'
        ]


class AlertAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging an alert."""

    def update(self, instance, validated_data):
        """Mark the alert as acknowledged."""
        from django.utils import timezone

        instance.acknowledged = True
        instance.acknowledged_at = timezone.now()
        instance.acknowledged_by = self.context['request'].user
        instance.save()

        return instance
