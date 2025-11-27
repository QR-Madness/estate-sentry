"""
Handler for door and window contact sensors.
"""
from .base import BaseSensorHandler


class ContactHandler(BaseSensorHandler):
    """
    Handler for door and window contact sensors.
    Processes open/close states and detects intrusion threats.
    """

    def validate_reading(self, data):
        """Validate contact sensor reading data."""
        if not isinstance(data, dict):
            return False, "Data must be a dictionary"

        if 'state' not in data:
            return False, "Missing 'state' field"

        if data['state'] not in ['open', 'closed']:
            return False, "State must be 'open' or 'closed'"

        return True, None

    def process_reading(self, data):
        """Process contact sensor reading."""
        return {
            'state': data['state'],
            'timestamp': data.get('timestamp'),
            'sensor_battery': data.get('battery_level'),
        }

    def detect_threats(self, reading):
        """Detect potential intrusion from contact sensor."""
        alerts = []

        if reading.value.get('state') == 'open':
            # Create an alert for open door/window
            alert_type = 'DOOR_OPEN' if self.sensor.sensor_type == 'DOOR_CONTACT' else 'WINDOW_OPEN'
            alerts.append({
                'alert_type': alert_type,
                'severity': 'MEDIUM',
                'title': f"{self.sensor.name} Opened",
                'description': f"The {self.sensor.location} {self.sensor.get_sensor_type_display().lower()} was opened.",
                'metadata': {
                    'reading_id': reading.id,
                    'timestamp': str(reading.timestamp),
                }
            })

        return alerts
