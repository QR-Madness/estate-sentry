from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.validators import for_field

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


#: Built once at import. Ingest is a hot path and these are reused per request.
_VALUE_VALIDATORS = for_field('sensor_reading.value')


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
        from .handlers.camera import CameraHandler
        from .handlers.contact import ContactHandler

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

        # Schema and size, checked on the *processed* value, because that is
        # what gets stored. This has to be explicit: the model field carries the
        # same validators, but this is a plain Serializer, not a
        # ModelSerializer, so DRF has no field to copy them onto — and
        # `objects.create()` never calls `full_clean()`. Without this the
        # model-level validators would be decorative on the ingest path.
        #
        # It matters most for the seven sensor types that have no handler: the
        # block above does not run for them, so this is the only thing standing
        # between the wire and the database.
        for validator in _VALUE_VALIDATORS:
            try:
                validator(data['value'])
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'value': exc.messages}) from exc

        return data

    def create(self, validated_data):
        """Create a sensor reading."""
        sensor = self.context['sensor']
        reading = SensorReading.objects.create(
            sensor=sensor,
            **validated_data
        )
        return reading
