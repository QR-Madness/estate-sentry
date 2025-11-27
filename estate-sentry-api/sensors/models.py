from django.db import models
from django.conf import settings


class Sensor(models.Model):
    """
    Represents a physical or virtual sensor device.
    Supports various sensor types for comprehensive home security monitoring.
    """

    SENSOR_TYPE_CHOICES = [
        ('CAMERA', 'Camera'),
        ('DOOR_CONTACT', 'Door Contact'),
        ('WINDOW_CONTACT', 'Window Contact'),
        ('GLASS_BREAK', 'Glass Break Sensor'),
        ('MOTION', 'Motion Detector'),
        ('SMOKE', 'Smoke Detector'),
        ('CO', 'Carbon Monoxide Detector'),
        ('WATER_LEAK', 'Water Leak Sensor'),
        ('TEMPERATURE', 'Temperature Sensor'),
        ('CUSTOM', 'Custom Sensor'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('MAINTENANCE', 'Maintenance'),
        ('ERROR', 'Error'),
    ]

    name = models.CharField(max_length=255, help_text='Human-readable sensor name')
    sensor_type = models.CharField(max_length=50, choices=SENSOR_TYPE_CHOICES)
    location = models.CharField(max_length=255, help_text='Physical location of the sensor')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    # Handler configuration
    handler_class = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Python path to the sensor handler class'
    )

    # Connection and configuration stored as JSON
    connection_config = models.JSONField(
        default=dict,
        help_text='Connection details (IP, port, credentials, etc.)'
    )

    metadata = models.JSONField(
        default=dict,
        help_text='Additional sensor metadata'
    )

    # Ownership and timestamps
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sensors'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sensors'
        verbose_name = 'Sensor'
        verbose_name_plural = 'Sensors'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_sensor_type_display()})"


class SensorReading(models.Model):
    """
    Time-series data from sensors.
    Stores raw sensor readings for analysis and threat detection.
    """

    sensor = models.ForeignKey(
        Sensor,
        on_delete=models.CASCADE,
        related_name='readings'
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Flexible value storage for different sensor types
    value = models.JSONField(
        help_text='Sensor reading value (format depends on sensor type)'
    )

    reading_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Type of reading (e.g., motion_detected, temperature, image)'
    )

    processed = models.BooleanField(
        default=False,
        help_text='Whether this reading has been processed for threat detection'
    )

    class Meta:
        db_table = 'sensor_readings'
        verbose_name = 'Sensor Reading'
        verbose_name_plural = 'Sensor Readings'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sensor', '-timestamp']),
            models.Index(fields=['processed']),
        ]

    def __str__(self):
        return f"{self.sensor.name} - {self.timestamp}"
