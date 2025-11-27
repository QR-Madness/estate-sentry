from django.db import models
from django.conf import settings


class Alert(models.Model):
    """
    Security alerts generated from sensor data and threat analysis.
    """

    ALERT_TYPE_CHOICES = [
        ('INTRUSION', 'Intrusion Detected'),
        ('MOTION', 'Motion Detected'),
        ('DOOR_OPEN', 'Door Opened'),
        ('WINDOW_OPEN', 'Window Opened'),
        ('GLASS_BREAK', 'Glass Break Detected'),
        ('SMOKE', 'Smoke Detected'),
        ('CO', 'Carbon Monoxide Detected'),
        ('WATER_LEAK', 'Water Leak Detected'),
        ('TEMPERATURE', 'Temperature Anomaly'),
        ('SYSTEM', 'System Alert'),
        ('CUSTOM', 'Custom Alert'),
    ]

    SEVERITY_CHOICES = [
        ('INFO', 'Informational'),
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)

    sensor = models.ForeignKey(
        'sensors.Sensor',
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        help_text='Sensor that triggered the alert (if applicable)'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text='User who owns this alert'
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    title = models.CharField(max_length=255)
    description = models.TextField()

    # Alert state management
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        help_text='Additional alert context and data'
    )

    class Meta:
        db_table = 'alerts'
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
            models.Index(fields=['acknowledged']),
        ]

    def __str__(self):
        return f"{self.get_severity_display()} - {self.title}"
