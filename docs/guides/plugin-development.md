# Plugin Development Guide

This guide explains how to create custom sensor handlers, protocol adapters, and device integrations for Estate Sentry.

## Overview

Estate Sentry uses a plugin-based architecture that allows you to:

- Add support for new sensor types
- Integrate with new communication protocols
- Implement custom threat detection logic
- Extend the system without modifying core code

## Creating a Sensor Handler

### Handler Structure

Every sensor handler inherits from `BaseSensorHandler`:

```python
# sensors/handlers/my_sensor.py
from typing import List, Tuple, Optional
from .base import BaseSensorHandler

class MySensorHandler(BaseSensorHandler):
    """Handler for my custom sensor type."""

    # Required: Sensor types this handler supports
    SENSOR_TYPES = ['MY_SENSOR_TYPE']

    # Optional: Supported communication protocols
    PROTOCOLS = ['mqtt', 'rest']

    # Optional: Handler version
    VERSION = '1.0.0'

    def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate incoming sensor data.

        Args:
            data: Raw sensor reading data

        Returns:
            Tuple of (is_valid, error_message)
            - If valid: (True, None)
            - If invalid: (False, "Error description")
        """
        # Implement your validation logic
        if 'required_field' not in data:
            return False, "Missing required_field"
        return True, None

    def process_reading(self, data: dict) -> dict:
        """
        Process and normalize sensor data.

        Args:
            data: Validated sensor reading data

        Returns:
            Normalized reading data for storage
        """
        return {
            'value': data['required_field'],
            'timestamp': data.get('timestamp'),
            'metadata': data.get('metadata', {})
        }

    def detect_threats(self, reading: dict) -> List[dict]:
        """
        Analyze reading for security threats.

        Args:
            reading: Processed sensor reading

        Returns:
            List of alert dictionaries
        """
        alerts = []

        # Implement threat detection logic
        if self._is_suspicious(reading):
            alerts.append({
                'alert_type': 'CUSTOM_ALERT',
                'severity': 'MEDIUM',
                'title': f"Alert from {self.sensor.name}",
                'description': "Suspicious activity detected",
                'metadata': {'reading': reading}
            })

        return alerts

    def _is_suspicious(self, reading: dict) -> bool:
        """Custom threat detection logic."""
        # Your logic here
        return False
```

### Handler Registration

Handlers are automatically discovered when placed in `sensors/handlers/`. The registry scans for classes that:

1. Inherit from `BaseSensorHandler`
2. Have a non-empty `SENSOR_TYPES` list
3. Are not the base class itself

To manually register (for external packages):

```python
# In your package's __init__.py
from sensors.registry import HandlerRegistry
from .my_handler import MySensorHandler

HandlerRegistry.register_handler(MySensorHandler)
```

Or use entry points in your `pyproject.toml`:

```toml
[project.entry-points."estate_sentry.handlers"]
my_sensor = "my_package.handlers:MySensorHandler"
```

### Adding Sensor Types

Add your sensor type to the model choices:

```python
# sensors/models.py
class Sensor(models.Model):
    class SensorType(models.TextChoices):
        # Existing types...
        MY_SENSOR_TYPE = 'MY_SENSOR_TYPE', 'My Custom Sensor'
```

### JSON Schema Validation

Define schemas for automatic validation:

```python
class MySensorHandler(BaseSensorHandler):
    # ...

    @classmethod
    def get_reading_schema(cls) -> dict:
        """JSON Schema for reading validation."""
        return {
            "type": "object",
            "properties": {
                "required_field": {
                    "type": "string",
                    "description": "Main sensor value"
                },
                "temperature": {
                    "type": "number",
                    "minimum": -50,
                    "maximum": 150
                },
                "battery_level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["required_field"]
        }

    @classmethod
    def get_connection_schema(cls) -> dict:
        """JSON Schema for connection configuration."""
        return {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "api_key": {"type": "string"}
            },
            "required": ["host"]
        }
```

## Creating a Protocol Adapter

Protocol adapters handle communication with devices using different protocols.

### Adapter Structure

```python
# devices/protocols/my_protocol.py
from typing import Callable, Any
from .base import BaseProtocolAdapter

class MyProtocolAdapter(BaseProtocolAdapter):
    """Adapter for my custom protocol."""

    PROTOCOL_NAME = "my_protocol"

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = None

    async def connect(self) -> bool:
        """Establish connection to device."""
        try:
            self.client = MyProtocolClient(
                host=self.config['host'],
                port=self.config.get('port', 1234)
            )
            await self.client.connect()
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Close connection."""
        if self.client:
            await self.client.disconnect()
        self._connected = False

    async def read(self) -> dict:
        """Read current state from device."""
        if not self._connected:
            raise RuntimeError("Not connected")

        response = await self.client.query()
        return {
            'value': response.value,
            'timestamp': response.timestamp
        }

    async def write(self, command: dict) -> bool:
        """Send command to device."""
        if not self._connected:
            return False

        try:
            await self.client.send(command)
            return True
        except Exception:
            return False

    async def subscribe(self, callback: Callable[[dict], Any]) -> None:
        """Subscribe to device updates."""
        async for message in self.client.stream():
            await callback({
                'value': message.value,
                'timestamp': message.timestamp
            })
```

### Protocol Registration

```python
from sensors.registry import HandlerRegistry

HandlerRegistry.register_protocol(MyProtocolAdapter)
```

## Complete Example: Glass Break Sensor

Here's a complete example of a glass break sensor handler:

```python
# sensors/handlers/glass_break.py
from typing import List, Tuple, Optional
from datetime import datetime
from .base import BaseSensorHandler

class GlassBreakHandler(BaseSensorHandler):
    """Handler for glass break detection sensors."""

    SENSOR_TYPES = ['GLASS_BREAK']
    PROTOCOLS = ['zigbee', 'zwave', 'rest']
    VERSION = '1.0.0'

    # Severity thresholds
    HIGH_INTENSITY_THRESHOLD = 80
    MEDIUM_INTENSITY_THRESHOLD = 50

    def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
        """Validate glass break sensor data."""
        # Must have either triggered flag or intensity
        if 'triggered' not in data and 'intensity' not in data:
            return False, "Reading must include 'triggered' or 'intensity'"

        # Validate intensity range
        if 'intensity' in data:
            intensity = data['intensity']
            if not isinstance(intensity, (int, float)):
                return False, "Intensity must be a number"
            if not 0 <= intensity <= 100:
                return False, "Intensity must be between 0 and 100"

        return True, None

    def process_reading(self, data: dict) -> dict:
        """Normalize glass break reading."""
        processed = {
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
            'triggered': data.get('triggered', False),
            'intensity': data.get('intensity', 0),
            'frequency': data.get('frequency'),  # Hz of detected sound
            'duration_ms': data.get('duration_ms'),  # Duration of event
        }

        # Infer triggered from intensity if not provided
        if 'triggered' not in data and 'intensity' in data:
            processed['triggered'] = data['intensity'] > self.MEDIUM_INTENSITY_THRESHOLD

        return processed

    def detect_threats(self, reading: dict) -> List[dict]:
        """Detect glass break threats."""
        alerts = []

        if not reading.get('triggered'):
            return alerts

        # Determine severity based on intensity
        intensity = reading.get('intensity', 50)

        if intensity >= self.HIGH_INTENSITY_THRESHOLD:
            severity = 'HIGH'
            description = "High-intensity glass break detected - possible forced entry"
        elif intensity >= self.MEDIUM_INTENSITY_THRESHOLD:
            severity = 'MEDIUM'
            description = "Glass break detected"
        else:
            severity = 'LOW'
            description = "Possible glass break detected (low intensity)"

        alerts.append({
            'alert_type': 'GLASS_BREAK',
            'severity': severity,
            'title': f"Glass break detected at {self.sensor.name}",
            'description': description,
            'metadata': {
                'sensor_id': str(self.sensor.id),
                'location': self.sensor.location,
                'intensity': intensity,
                'frequency': reading.get('frequency'),
                'duration_ms': reading.get('duration_ms'),
            }
        })

        return alerts

    @classmethod
    def get_reading_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "triggered": {
                    "type": "boolean",
                    "description": "Whether glass break was detected"
                },
                "intensity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Intensity of detected break (0-100)"
                },
                "frequency": {
                    "type": "number",
                    "description": "Frequency of detected sound in Hz"
                },
                "duration_ms": {
                    "type": "integer",
                    "description": "Duration of detected event in milliseconds"
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time"
                }
            }
        }

    @classmethod
    def get_connection_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "protocol": {
                    "type": "string",
                    "enum": ["zigbee", "zwave", "rest"]
                },
                "device_id": {
                    "type": "string",
                    "description": "Device identifier on the network"
                },
                "sensitivity": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Detection sensitivity (1-10)"
                }
            },
            "required": ["device_id"]
        }
```

## Testing Handlers

### Unit Tests

```python
# sensors/tests/test_glass_break_handler.py
import pytest
from sensors.handlers.glass_break import GlassBreakHandler
from sensors.models import Sensor

@pytest.fixture
def sensor():
    return Sensor(
        name="Test Glass Break",
        sensor_type="GLASS_BREAK",
        location="Living Room"
    )

@pytest.fixture
def handler(sensor):
    return GlassBreakHandler(sensor)

class TestGlassBreakHandler:

    def test_validate_valid_reading(self, handler):
        data = {"triggered": True, "intensity": 75}
        is_valid, error = handler.validate_reading(data)
        assert is_valid is True
        assert error is None

    def test_validate_missing_required(self, handler):
        data = {"extra_field": "value"}
        is_valid, error = handler.validate_reading(data)
        assert is_valid is False
        assert "triggered" in error or "intensity" in error

    def test_validate_invalid_intensity(self, handler):
        data = {"intensity": 150}
        is_valid, error = handler.validate_reading(data)
        assert is_valid is False
        assert "intensity" in error.lower()

    def test_process_reading(self, handler):
        data = {"triggered": True, "intensity": 80}
        processed = handler.process_reading(data)
        assert processed['triggered'] is True
        assert processed['intensity'] == 80
        assert 'timestamp' in processed

    def test_detect_threats_high_intensity(self, handler):
        reading = {"triggered": True, "intensity": 90}
        alerts = handler.detect_threats(reading)
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'HIGH'
        assert alerts[0]['alert_type'] == 'GLASS_BREAK'

    def test_detect_threats_no_trigger(self, handler):
        reading = {"triggered": False, "intensity": 0}
        alerts = handler.detect_threats(reading)
        assert len(alerts) == 0
```

### Integration Tests

```python
# sensors/tests/test_handler_integration.py
from rest_framework.test import APITestCase
from authentication.models import User
from sensors.models import Sensor

class GlassBreakIntegrationTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)

        self.sensor = Sensor.objects.create(
            owner=self.user,
            name="Living Room Glass Break",
            sensor_type="GLASS_BREAK",
            location="Living Room",
            status="ACTIVE"
        )

    def test_submit_reading_creates_alert(self):
        response = self.client.post(
            f'/api/sensors/{self.sensor.id}/readings/',
            {'value': {'triggered': True, 'intensity': 85}},
            format='json'
        )
        self.assertEqual(response.status_code, 201)

        # Verify alert was created
        from alerts.models import Alert
        alerts = Alert.objects.filter(sensor=self.sensor)
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts[0].alert_type, 'GLASS_BREAK')
        self.assertEqual(alerts[0].severity, 'HIGH')
```

## Best Practices

### 1. Validate Thoroughly

Always validate all expected fields:

```python
def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
    errors = []

    if 'state' not in data:
        errors.append("Missing 'state' field")

    if 'state' in data and data['state'] not in ['on', 'off']:
        errors.append("Invalid state value")

    if errors:
        return False, "; ".join(errors)

    return True, None
```

### 2. Handle Missing Data Gracefully

```python
def process_reading(self, data: dict) -> dict:
    return {
        'value': data['value'],
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
        'battery': data.get('battery_level'),  # May be None
        'signal': data.get('signal_strength'),  # May be None
    }
```

### 3. Use Appropriate Severity Levels

| Severity | Use Case |
|----------|----------|
| CRITICAL | Immediate danger, requires instant response |
| HIGH | Serious threat, requires quick response |
| MEDIUM | Potential threat, requires attention |
| LOW | Minor concern, informational |
| INFO | Status update, no action required |

### 4. Include Context in Alerts

```python
def detect_threats(self, reading: dict) -> List[dict]:
    return [{
        'alert_type': 'MY_ALERT',
        'severity': 'MEDIUM',
        'title': f"Alert from {self.sensor.name}",
        'description': f"Detected at {self.sensor.location}",
        'metadata': {
            'sensor_id': str(self.sensor.id),
            'sensor_type': self.sensor.sensor_type,
            'location': self.sensor.location,
            'reading': reading,
            'timestamp': datetime.utcnow().isoformat()
        }
    }]
```

### 5. Document Your Handler

```python
class MySensorHandler(BaseSensorHandler):
    """
    Handler for XYZ brand motion sensors.

    Supported models:
    - XYZ-100: Basic motion detection
    - XYZ-200: Motion + temperature

    Reading format:
    {
        "motion": true,
        "temperature": 72.5,
        "battery": 85
    }

    Connection config:
    {
        "device_id": "XYZ-100-001",
        "protocol": "zigbee"
    }
    """
```

## Related Documentation

- [Device Abstraction Architecture](../architecture/device-abstraction.md)
- [API Usage Guide](api-usage.md)
- [Development Guide](../contributing/development.md)
