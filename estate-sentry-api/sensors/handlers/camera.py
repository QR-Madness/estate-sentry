"""
Handler for camera sensors.
Placeholder for future single-shot recognition implementation.
"""
from .base import BaseSensorHandler


class CameraHandler(BaseSensorHandler):
    """
    Handler for camera sensors.
    Currently a skeleton for future ML-based threat detection.
    """

    def validate_reading(self, data):
        """Validate camera sensor reading data."""
        if not isinstance(data, dict):
            return False, "Data must be a dictionary"

        # For now, we just accept image_url or motion_detected
        if 'image_url' not in data and 'motion_detected' not in data:
            return False, "Must include 'image_url' or 'motion_detected'"

        return True, None

    def process_reading(self, data):
        """Process camera sensor reading."""
        return {
            'image_url': data.get('image_url'),
            'motion_detected': data.get('motion_detected', False),
            'timestamp': data.get('timestamp'),
            'metadata': data.get('metadata', {}),
        }

    def detect_threats(self, reading):
        """
        Detect threats from camera data.
        TODO: Implement single-shot recognition here in the future.
        """
        alerts = []

        if reading.value.get('motion_detected'):
            alerts.append({
                'alert_type': 'MOTION',
                'severity': 'LOW',
                'title': f"Motion Detected at {self.sensor.name}",
                'description': f"Motion was detected by camera at {self.sensor.location}.",
                'metadata': {
                    'reading_id': reading.id,
                    'image_url': reading.value.get('image_url'),
                    'timestamp': str(reading.timestamp),
                }
            })

        return alerts
