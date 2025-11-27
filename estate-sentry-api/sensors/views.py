from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Sensor, SensorReading
from .serializers import (
    SensorSerializer,
    SensorReadingSerializer,
    SensorReadingCreateSerializer
)


class SensorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing sensors.
    """
    serializer_class = SensorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return sensors owned by the current user."""
        return Sensor.objects.filter(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def readings(self, request, pk=None):
        """
        Submit a new sensor reading.
        POST /api/sensors/{id}/readings/
        """
        sensor = self.get_object()

        serializer = SensorReadingCreateSerializer(
            data=request.data,
            context={'sensor': sensor, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        reading = serializer.save()

        # Process the reading for threat detection
        self._process_reading_for_threats(reading)

        return Response(
            SensorReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'])
    def reading_history(self, request, pk=None):
        """
        Get sensor reading history.
        GET /api/sensors/{id}/reading_history/
        """
        sensor = self.get_object()
        readings = sensor.readings.all()[:100]  # Last 100 readings

        serializer = SensorReadingSerializer(readings, many=True)
        return Response(serializer.data)

    def _process_reading_for_threats(self, reading):
        """
        Process a sensor reading to detect threats and create alerts.
        """
        from .handlers.contact import ContactHandler
        from .handlers.camera import CameraHandler
        from alerts.models import Alert

        handler_map = {
            'DOOR_CONTACT': ContactHandler,
            'WINDOW_CONTACT': ContactHandler,
            'CAMERA': CameraHandler,
        }

        handler_class = handler_map.get(reading.sensor.sensor_type)

        if handler_class:
            handler = handler_class(reading.sensor)
            alerts_data = handler.detect_threats(reading)

            # Create alerts if any threats detected
            for alert_data in alerts_data:
                Alert.objects.create(
                    user=reading.sensor.owner,
                    sensor=reading.sensor,
                    **alert_data
                )

        # Mark reading as processed
        reading.processed = True
        reading.save()


class SensorReadingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing sensor readings.
    """
    serializer_class = SensorReadingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return readings for sensors owned by the current user."""
        return SensorReading.objects.filter(sensor__owner=self.request.user)
