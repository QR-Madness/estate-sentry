from rest_framework import serializers
from .models import Sensor, SensorReading


class SensorSerializer(serializers.ModelSerializer):
    """Serializer for Sensor model."""

    owner_username = serializers.CharField(source='owner.username', read_only=True)
    sensor_type_display = serializers.CharField(source='get_sensor_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Sensor
        fields = [
            'id', 'name', 'sensor_type', 'sensor_type_display', 'location',
            'status', 'status_display', 'handler_class', 'connection_config',
            'metadata', 'owner', 'owner_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Set the owner to the current user."""
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class SensorReadingSerializer(serializers.ModelSerializer):
    """Serializer for SensorReading model."""

    sensor_name = serializers.CharField(source='sensor.name', read_only=True)

    class Meta:
        model = SensorReading
        fields = [
            'id', 'sensor', 'sensor_name', 'timestamp', 'value',
            'reading_type', 'processed'
        ]
        read_only_fields = ['id', 'timestamp', 'processed']


class SensorReadingCreateSerializer(serializers.Serializer):
    """Serializer for creating sensor readings with validation."""

    value = serializers.JSONField()
    reading_type = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate the reading data using the sensor's handler."""
        sensor = self.context.get('sensor')

        if not sensor:
            raise serializers.ValidationError("Sensor context is required")

        # Get the appropriate handler for this sensor type
        from .handlers.contact import ContactHandler
        from .handlers.camera import CameraHandler

        handler_map = {
            'DOOR_CONTACT': ContactHandler,
            'WINDOW_CONTACT': ContactHandler,
            'CAMERA': CameraHandler,
        }

        handler_class = handler_map.get(sensor.sensor_type)

        if handler_class:
            handler = handler_class(sensor)
            is_valid, error_message = handler.validate_reading(data['value'])

            if not is_valid:
                raise serializers.ValidationError({'value': error_message})

            # Process the reading data
            data['value'] = handler.process_reading(data['value'])

        return data

    def create(self, validated_data):
        """Create a sensor reading."""
        sensor = self.context['sensor']
        reading = SensorReading.objects.create(
            sensor=sensor,
            **validated_data
        )
        return reading
