"""
Base sensor handler class that all specific sensor handlers inherit from.
"""
from abc import ABC, abstractmethod


class BaseSensorHandler(ABC):
    """
    Abstract base class for sensor handlers.
    Each sensor type should have its own handler class inheriting from this.
    """

    def __init__(self, sensor):
        """
        Initialize the handler with a sensor instance.

        Args:
            sensor: The Sensor model instance
        """
        self.sensor = sensor

    @abstractmethod
    def validate_reading(self, data):
        """
        Validate incoming sensor reading data.

        Args:
            data: Raw sensor reading data

        Returns:
            Tuple of (is_valid: bool, error_message: str or None)
        """
        pass

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
            reading: SensorReading model instance

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
        }
