from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.validators import for_field

from .models import Sensor, SensorReading
from .signing import SIGNATURE_HEADER, SignatureError, enforce_policy


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
            'metadata', 'public_key', 'require_signature', 'owner',
            'owner_username', 'created_at', 'updated_at'
        ]
        # `public_key` and `require_signature` are visible but not settable.
        # Enrolling a key is an out-of-band act, like enrolling a trusted
        # device: if the account token could rotate the key, an attacker holding
        # that token could simply install their own and sign whatever they
        # liked. Use `manage.py enroll_sensor_key`.
        read_only_fields = [
            'id', 'owner', 'created_at', 'updated_at',
            'public_key', 'require_signature',
        ]

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

    # Signature material. Write-only and popped before the row is built: these
    # authenticate the reading, they are not part of it.
    nonce = serializers.CharField(
        required=False, allow_blank=True, max_length=128, write_only=True
    )
    signed_at = serializers.CharField(
        required=False, allow_blank=True, max_length=64, write_only=True
    )

    def validate(self, data):
        """Validate the reading data using the sensor's handler."""
        sensor = self.context.get('sensor')

        if not sensor:
            raise serializers.ValidationError("Sensor context is required")

        # Authenticity first, and against the *raw* value: the device signed
        # what it sent, not the shape the handler will normalise it into. This
        # also means a forged reading is refused before any handler runs on it.
        nonce = data.pop('nonce', '')
        signed_at = data.pop('signed_at', '')
        request = self.context.get('request')
        signature = (
            request.META.get(SIGNATURE_HEADER, '') if request is not None else ''
        )

        try:
            enforce_policy(sensor, signature, nonce, signed_at, data['value'])
        except SignatureError as exc:
            raise serializers.ValidationError({'signature': str(exc)}) from exc

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
