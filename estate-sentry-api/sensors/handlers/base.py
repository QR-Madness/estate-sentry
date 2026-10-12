"""
Base sensor handler class that all specific sensor handlers inherit from.

A handler owns everything type-specific about a sensor's readings: what shape
they arrive in, how they are normalised for storage, and what in them counts as
a threat. Handlers are registered by sensor type in `sensors.registry`, which
finds the ones defined in this package on its own — see
`docs/guides/plugin-development.md`.
"""
from abc import ABC, abstractmethod
from functools import cache

from jsonschema import Draft202012Validator


@cache
def _compiled(handler_cls, kind):
    """The handler's schema of the given kind, compiled once.

    Keyed by class, so a subclass gets its own entry. `check_schema` runs here,
    and the registry calls this at registration, so a malformed schema stops the
    app at startup rather than surfacing on the first reading that hits it.
    """
    if kind == 'reading':
        schema = handler_cls.get_reading_schema()
    elif kind == 'connection':
        schema = handler_cls.get_connection_schema()
    else:
        raise ValueError(f'unknown schema kind {kind!r}')

    if schema is None:
        return None
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schema_errors(handler_cls, kind, instance):
    """Every way `instance` fails the handler's schema, as readable messages.

    Every problem at once rather than the first, so a device integrator fixing a
    payload does not discover the next one on each retry. Empty when the handler
    declares no schema of that kind.
    """
    validator = _compiled(handler_cls, kind)
    if validator is None:
        return []
    return [
        f'{error.json_path}: {error.message}'
        for error in sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    ]


class BaseSensorHandler(ABC):
    """
    Abstract base class for sensor handlers.
    Each sensor type should have its own handler class inheriting from this.
    """

    #: Sensor types this handler serves. Required for registration: a handler
    #: with none is treated as an abstract helper and never registered.
    SENSOR_TYPES = []

    #: Transport protocols the handler's devices speak. Descriptive only for now;
    #: the protocol adapters that would act on it are deferred to the sensor kit.
    PROTOCOLS = []

    VERSION = '1.0.0'

    def __init__(self, sensor):
        """
        Initialize the handler with a sensor instance.

        Args:
            sensor: The Sensor model instance
        """
        self.sensor = sensor

    @classmethod
    def get_reading_schema(cls):
        """JSON Schema for a raw reading, before `process_reading`. None for none."""
        return None

    @classmethod
    def get_connection_schema(cls):
        """JSON Schema for `Sensor.connection_config` on sensors of this type.

        Applied on top of the generic schema every config already passes. None
        adds nothing, which is the right default for a device that pushes its own
        readings and needs no connection details at all.
        """
        return None

    def validate_reading(self, data):
        """
        Validate incoming sensor reading data.

        The default checks `get_reading_schema()`, so a handler that declares a
        schema gets validation for free. Override to add checks a schema cannot
        express, calling `super()` first to keep the schema's.

        Args:
            data: Raw sensor reading data

        Returns:
            Tuple of (is_valid: bool, error_message: str or None)
        """
        errors = schema_errors(type(self), 'reading', data)
        if errors:
            return False, '; '.join(errors)
        return True, None

    @abstractmethod
    def process_reading(self, data):
        """
        Process and normalize sensor reading data.

        Args:
            data: Raw sensor reading data

        Returns:
            Processed data ready to be stored
        """
        pass

    def detect_threats(self, reading):
        """
        Analyze sensor reading for potential threats.
        This is optional and can be overridden by specific handlers.

        Args:
            reading: SensorReading model instance — the processed value is
                `reading.value`, and `reading.id` / `reading.timestamp` are
                available for the alert's metadata

        Returns:
            List of Alert dictionaries if threats detected, empty list otherwise
        """
        return []

    def get_handler_info(self):
        """
        Return information about this handler.

        Returns:
            Dict with handler metadata
        """
        return {
            'handler_class': self.__class__.__name__,
            'sensor_type': self.sensor.sensor_type,
            'sensor_name': self.sensor.name,
            'version': self.VERSION,
        }
