# Device Abstraction Layer

Estate Sentry's device abstraction layer provides a unified interface for interacting with diverse security devices, from simple contact sensors to complex camera systems and industrial PLCs. This architecture enables extensibility without modifying core system code.

## Overview

```
+-------------------------------------------------------------------+
|                        Device Abstraction Layer                    |
|  +------------------+  +------------------+  +------------------+  |
|  |  Handler Registry|  | Protocol Adapters|  |  Device Models   |  |
|  +------------------+  +------------------+  +------------------+  |
+-------------------------------------------------------------------+
         |                        |                       |
+--------v-------+    +-----------v---------+    +--------v-------+
|  Sensor        |    |  MQTT Adapter       |    |  Sensor Model  |
|  Handlers      |    |  REST Adapter       |    |  Actuator Model|
|  (contact,     |    |  Modbus Adapter     |    |  Controller    |
|   camera, etc) |    |  WebSocket Adapter  |    |  Model         |
+----------------+    +---------------------+    +----------------+
```

## Device Hierarchy

### Device Types

Estate Sentry categorizes devices into three primary types:

| Type | Direction | Examples |
|------|-----------|----------|
| **Sensor** | Read-only | Cameras, contacts, motion, environmental |
| **Actuator** | Write/Control | Lights, locks, sirens, relays |
| **Controller** | Bidirectional | PLCs, hubs, gateways |

### Device Model

```python
# devices/models.py
class DeviceType(models.TextChoices):
    # Sensors (read-only)
    SENSOR_CAMERA = 'SENSOR_CAMERA'
    SENSOR_CONTACT = 'SENSOR_CONTACT'
    SENSOR_MOTION = 'SENSOR_MOTION'
    SENSOR_GLASS_BREAK = 'SENSOR_GLASS_BREAK'
    SENSOR_ENVIRONMENTAL = 'SENSOR_ENVIRONMENTAL'

    # Actuators (write/control)
    ACTUATOR_LIGHT = 'ACTUATOR_LIGHT'
    ACTUATOR_LOCK = 'ACTUATOR_LOCK'
    ACTUATOR_SIREN = 'ACTUATOR_SIREN'
    ACTUATOR_RELAY = 'ACTUATOR_RELAY'

    # Controllers (bidirectional)
    CONTROLLER_PLC = 'CONTROLLER_PLC'
    CONTROLLER_HUB = 'CONTROLLER_HUB'
    CONTROLLER_GATEWAY = 'CONTROLLER_GATEWAY'

class Device(models.Model):
    """Base device model for all device types."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50, choices=DeviceType.choices)
    location = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default='INACTIVE')

    # Handler configuration
    handler_class = models.CharField(max_length=255)
    protocol = models.CharField(max_length=50)

    # Flexible configuration
    connection_config = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Handler Registry

The handler registry provides auto-discovery and registration of device handlers.

### Registry Implementation

```python
# sensors/registry.py
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type, Optional

class HandlerRegistry:
    """Central registry for sensor and device handlers."""

    _instance = None
    _handlers: Dict[str, Type['BaseSensorHandler']] = {}
    _protocols: Dict[str, Type['BaseProtocolAdapter']] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._discovered = False
        return cls._instance

    @classmethod
    def discover(cls):
        """Auto-discover handlers from the handlers package."""
        if cls._instance._discovered:
            return

        # Discover handlers in sensors/handlers/
        handlers_path = Path(__file__).parent / 'handlers'
        for module_info in pkgutil.iter_modules([str(handlers_path)]):
            if module_info.name.startswith('_'):
                continue

            module = importlib.import_module(
                f'sensors.handlers.{module_info.name}'
            )

            # Find handler classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseSensorHandler) and
                    attr is not BaseSensorHandler):
                    cls.register_handler(attr)

        cls._instance._discovered = True

    @classmethod
    def register_handler(cls, handler_class: Type['BaseSensorHandler']):
        """Register a handler class."""
        for sensor_type in handler_class.SENSOR_TYPES:
            cls._handlers[sensor_type] = handler_class

    @classmethod
    def get_handler(cls, sensor_type: str) -> Optional[Type['BaseSensorHandler']]:
        """Get handler class for a sensor type."""
        cls.discover()
        return cls._handlers.get(sensor_type)

    @classmethod
    def get_all_handlers(cls) -> Dict[str, Type['BaseSensorHandler']]:
        """Get all registered handlers."""
        cls.discover()
        return cls._handlers.copy()

    @classmethod
    def register_protocol(cls, protocol_class: Type['BaseProtocolAdapter']):
        """Register a protocol adapter."""
        cls._protocols[protocol_class.PROTOCOL_NAME] = protocol_class

    @classmethod
    def get_protocol(cls, protocol_name: str) -> Optional[Type['BaseProtocolAdapter']]:
        """Get protocol adapter for a protocol name."""
        return cls._protocols.get(protocol_name)
```

### Usage in Views

```python
# sensors/views.py
from .registry import HandlerRegistry

class SensorViewSet(viewsets.ModelViewSet):
    def _process_reading(self, sensor, reading_data):
        handler_class = HandlerRegistry.get_handler(sensor.sensor_type)
        if not handler_class:
            raise ValueError(f"No handler for sensor type: {sensor.sensor_type}")

        handler = handler_class(sensor)
        is_valid, error = handler.validate_reading(reading_data)
        if not is_valid:
            raise ValidationError(error)

        processed = handler.process_reading(reading_data)
        threats = handler.detect_threats(processed)

        return processed, threats
```

## Handler Interface

### Base Handler

```python
# sensors/handlers/base.py
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional

class BaseSensorHandler(ABC):
    """Abstract base class for all sensor handlers."""

    # Class-level metadata for auto-registration
    SENSOR_TYPES: List[str] = []  # e.g., ['DOOR_CONTACT', 'WINDOW_CONTACT']
    PROTOCOLS: List[str] = []      # e.g., ['mqtt', 'rest']
    VERSION: str = '1.0.0'

    def __init__(self, sensor):
        self.sensor = sensor

    @abstractmethod
    def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate incoming sensor data.

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def process_reading(self, data: dict) -> dict:
        """
        Process and normalize sensor data.

        Returns:
            Normalized reading data
        """
        pass

    def detect_threats(self, reading: dict) -> List[dict]:
        """
        Analyze reading for threats.

        Returns:
            List of alert dictionaries
        """
        return []

    @classmethod
    def get_reading_schema(cls) -> dict:
        """
        Return JSON Schema for reading validation.

        Override this to provide automatic validation.
        """
        return {"type": "object"}

    @classmethod
    def get_connection_schema(cls) -> dict:
        """
        Return JSON Schema for connection configuration.
        """
        return {"type": "object"}

    @classmethod
    def get_handler_info(cls) -> dict:
        """Return handler metadata."""
        return {
            'sensor_types': cls.SENSOR_TYPES,
            'protocols': cls.PROTOCOLS,
            'version': cls.VERSION,
            'reading_schema': cls.get_reading_schema(),
            'connection_schema': cls.get_connection_schema(),
        }
```

### Contact Handler Example

```python
# sensors/handlers/contact.py
class ContactHandler(BaseSensorHandler):
    """Handler for door and window contact sensors."""

    SENSOR_TYPES = ['DOOR_CONTACT', 'WINDOW_CONTACT']
    PROTOCOLS = ['mqtt', 'rest', 'zigbee']
    VERSION = '1.0.0'

    def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
        if 'state' not in data:
            return False, "Missing required field: state"

        if data['state'] not in ['open', 'closed']:
            return False, "State must be 'open' or 'closed'"

        return True, None

    def process_reading(self, data: dict) -> dict:
        return {
            'state': data['state'],
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
            'battery_level': data.get('battery_level'),
        }

    def detect_threats(self, reading: dict) -> List[dict]:
        alerts = []

        if reading['state'] == 'open':
            alert_type = 'DOOR_OPEN' if 'DOOR' in self.sensor.sensor_type else 'WINDOW_OPEN'
            alerts.append({
                'alert_type': alert_type,
                'severity': 'MEDIUM',
                'title': f"{self.sensor.name} opened",
                'description': f"Contact sensor detected {self.sensor.name} is now open",
                'metadata': {
                    'sensor_id': str(self.sensor.id),
                    'state': reading['state'],
                }
            })

        return alerts

    @classmethod
    def get_reading_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["open", "closed"]},
                "battery_level": {"type": "integer", "minimum": 0, "maximum": 100},
                "timestamp": {"type": "string", "format": "date-time"},
            },
            "required": ["state"]
        }
```

### Camera Handler Example

```python
# sensors/handlers/camera.py
class CameraHandler(BaseSensorHandler):
    """Handler for camera sensors."""

    SENSOR_TYPES = ['CAMERA']
    PROTOCOLS = ['rtsp', 'rest', 'websocket']
    VERSION = '1.0.0'

    def validate_reading(self, data: dict) -> Tuple[bool, Optional[str]]:
        if not data.get('frame_path') and not data.get('motion_detected'):
            return False, "Either frame_path or motion_detected is required"
        return True, None

    def process_reading(self, data: dict) -> dict:
        return {
            'frame_path': data.get('frame_path'),
            'motion_detected': data.get('motion_detected', False),
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
            'resolution': data.get('resolution'),
            'metadata': data.get('metadata', {}),
        }

    def detect_threats(self, reading: dict) -> List[dict]:
        alerts = []

        if reading.get('motion_detected'):
            alerts.append({
                'alert_type': 'MOTION',
                'severity': 'LOW',
                'title': f"Motion detected on {self.sensor.name}",
                'description': f"Camera {self.sensor.name} detected motion",
                'metadata': {
                    'sensor_id': str(self.sensor.id),
                    'frame_path': reading.get('frame_path'),
                }
            })

        return alerts

    @classmethod
    def get_connection_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "stream_url": {"type": "string", "format": "uri"},
                "fps": {"type": "integer", "minimum": 1, "maximum": 30},
                "resolution": {"type": "string", "enum": ["720p", "1080p", "4k"]},
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["stream_url"]
        }
```

## Protocol Adapters

Protocol adapters abstract communication with different device protocols.

### Base Protocol Adapter

```python
# devices/protocols/base.py
from abc import ABC, abstractmethod
from typing import Callable, Any

class BaseProtocolAdapter(ABC):
    """Abstract base class for protocol adapters."""

    PROTOCOL_NAME: str = ""

    def __init__(self, config: dict):
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the device."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the device."""
        pass

    @abstractmethod
    async def read(self) -> dict:
        """Read current state from device."""
        pass

    @abstractmethod
    async def write(self, command: dict) -> bool:
        """Write command to device (for actuators)."""
        pass

    @abstractmethod
    async def subscribe(self, callback: Callable[[dict], Any]) -> None:
        """Subscribe to device updates."""
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected
```

### MQTT Adapter

```python
# devices/protocols/mqtt.py
import asyncio_mqtt as aiomqtt

class MQTTProtocolAdapter(BaseProtocolAdapter):
    """MQTT protocol adapter for IoT devices."""

    PROTOCOL_NAME = "mqtt"

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = None
        self.topic = config.get('topic')

    async def connect(self) -> bool:
        self.client = aiomqtt.Client(
            hostname=self.config['host'],
            port=self.config.get('port', 1883),
            username=self.config.get('username'),
            password=self.config.get('password'),
        )
        await self.client.__aenter__()
        self._connected = True
        return True

    async def disconnect(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)
        self._connected = False

    async def read(self) -> dict:
        # MQTT is push-based, use subscribe instead
        raise NotImplementedError("Use subscribe for MQTT")

    async def write(self, command: dict) -> bool:
        if not self._connected:
            return False
        await self.client.publish(
            f"{self.topic}/command",
            json.dumps(command)
        )
        return True

    async def subscribe(self, callback: Callable[[dict], Any]) -> None:
        async with self.client.messages() as messages:
            await self.client.subscribe(f"{self.topic}/#")
            async for message in messages:
                data = json.loads(message.payload)
                await callback(data)
```

### Modbus Adapter (for PLCs)

```python
# devices/protocols/modbus.py
from pymodbus.client import AsyncModbusTcpClient

class ModbusProtocolAdapter(BaseProtocolAdapter):
    """Modbus TCP adapter for PLCs and industrial devices."""

    PROTOCOL_NAME = "modbus"

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = None
        self.unit_id = config.get('unit_id', 1)

    async def connect(self) -> bool:
        self.client = AsyncModbusTcpClient(
            host=self.config['host'],
            port=self.config.get('port', 502),
        )
        await self.client.connect()
        self._connected = self.client.connected
        return self._connected

    async def disconnect(self) -> None:
        if self.client:
            self.client.close()
        self._connected = False

    async def read(self) -> dict:
        """Read holding registers."""
        address = self.config.get('address', 0)
        count = self.config.get('count', 1)

        result = await self.client.read_holding_registers(
            address=address,
            count=count,
            slave=self.unit_id
        )

        if result.isError():
            raise IOError(f"Modbus read error: {result}")

        return {
            'registers': result.registers,
            'address': address,
            'timestamp': datetime.utcnow().isoformat()
        }

    async def write(self, command: dict) -> bool:
        """Write to holding registers."""
        address = command.get('address', 0)
        values = command.get('values', [])

        result = await self.client.write_registers(
            address=address,
            values=values,
            slave=self.unit_id
        )

        return not result.isError()

    async def subscribe(self, callback: Callable[[dict], Any]) -> None:
        """Poll registers at configured interval."""
        interval = self.config.get('poll_interval', 1.0)
        while self._connected:
            data = await self.read()
            await callback(data)
            await asyncio.sleep(interval)
```

## Adding Custom Handlers

### Via Python Package

Create a new handler in the `sensors/handlers/` directory:

```python
# sensors/handlers/custom_sensor.py
from .base import BaseSensorHandler

class CustomSensorHandler(BaseSensorHandler):
    SENSOR_TYPES = ['CUSTOM_TYPE']
    PROTOCOLS = ['rest']
    VERSION = '1.0.0'

    def validate_reading(self, data: dict):
        # Your validation logic
        return True, None

    def process_reading(self, data: dict):
        # Your processing logic
        return data

    def detect_threats(self, reading: dict):
        # Your threat detection logic
        return []
```

### Via Entry Points (Plugins)

For external packages, use Python entry points:

```toml
# pyproject.toml (external package)
[project.entry-points."estate_sentry.handlers"]
custom_handler = "my_package.handlers:CustomHandler"
```

The registry automatically discovers entry point-based handlers.

## Device Lifecycle

### Registration

```python
# API: POST /api/devices/
{
    "name": "Front Door Lock",
    "device_type": "ACTUATOR_LOCK",
    "location": "Main Entrance",
    "protocol": "mqtt",
    "connection_config": {
        "host": "mqtt.local",
        "topic": "locks/front_door"
    }
}
```

### Discovery

```python
# API: GET /api/devices/discover/
# Returns devices found on the network (protocol-specific)
{
    "discovered": [
        {
            "address": "192.168.1.100",
            "type": "SENSOR_CAMERA",
            "protocol": "rtsp",
            "name": "IP Camera"
        }
    ]
}
```

### Health Monitoring

```python
# API: GET /api/devices/{id}/health/
{
    "status": "ACTIVE",
    "last_seen": "2025-01-23T10:00:00Z",
    "battery_level": 85,
    "signal_strength": -45,
    "errors": []
}
```

## Related Documentation

- [Plugin Development Guide](../guides/plugin-development.md) - Creating custom handlers
- [Switchboard Architecture](switchboard.md) - Data routing for devices
- [API Usage](../guides/api-usage.md) - Device API endpoints
