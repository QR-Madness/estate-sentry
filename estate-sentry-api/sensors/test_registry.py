"""The handler registry.

Weighted towards the failures it exists to prevent. Every guard here stops a
handler that would otherwise register and then quietly do nothing — or worse,
let readings through unvalidated — which is the state seven of ten sensor types
were in before the registry existed.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from alerts.models import Alert
from authentication.models import User

from .handlers.base import BaseSensorHandler, schema_errors
from .handlers.camera import CameraHandler
from .handlers.contact import ContactHandler
from .models import Sensor, SensorReading
from .registry import ENTRY_POINT_GROUP, HandlerRegistry

TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'estate-sentry-tests',
    }
}


class SchemaOnlyHandler(BaseSensorHandler):
    """Validates by schema alone — no validate_reading override."""

    SENSOR_TYPES = ['CUSTOM']

    @classmethod
    def get_reading_schema(cls):
        return {
            'type': 'object',
            'properties': {'level': {'type': 'integer', 'minimum': 0, 'maximum': 10}},
            'required': ['level'],
        }

    @classmethod
    def get_connection_schema(cls):
        return {
            'type': 'object',
            'properties': {'device_id': {'type': 'string', 'minLength': 1}},
            'required': ['device_id'],
        }

    def process_reading(self, data):
        return {'level': data['level']}

    def detect_threats(self, reading):
        if reading.value['level'] >= 8:
            return [{
                'alert_type': 'CUSTOM', 'severity': 'HIGH',
                'title': 'High level', 'description': 'Level at or above 8.',
                'metadata': {'reading_id': reading.id},
            }]
        return []


class RegistryTestCase(TestCase):
    """Restores the registry after each test, since its state is class-level."""

    def setUp(self):
        saved = dict(HandlerRegistry._handlers)

        def restore():
            HandlerRegistry._handlers.clear()
            HandlerRegistry._handlers.update(saved)

        self.addCleanup(restore)


class DiscoveryTests(RegistryTestCase):
    def test_the_built_in_handlers_are_discovered_at_startup(self):
        self.assertIs(HandlerRegistry.get_handler('DOOR_CONTACT'), ContactHandler)
        self.assertIs(HandlerRegistry.get_handler('WINDOW_CONTACT'), ContactHandler)
        self.assertIs(HandlerRegistry.get_handler('CAMERA'), CameraHandler)

    def test_custom_has_no_handler(self):
        """By design: a custom sensor's payload is the integrator's to define."""
        self.assertIsNone(HandlerRegistry.get_handler('CUSTOM'))

    def test_autodiscovery_is_idempotent(self):
        before = dict(HandlerRegistry._handlers)

        HandlerRegistry.autodiscover()

        self.assertEqual(HandlerRegistry._handlers, before)

    def test_a_handler_instance_is_bound_to_its_sensor(self):
        owner = User.objects.create_user(username='o', password='x' * 12)
        sensor = Sensor.objects.create(
            name='Door', sensor_type='DOOR_CONTACT', location='Front', owner=owner,
        )

        handler = HandlerRegistry.get_handler_for(sensor)

        self.assertIsInstance(handler, ContactHandler)
        self.assertIs(handler.sensor, sensor)


class RegistrationGuardTests(RegistryTestCase):
    """Each guard refuses a handler that would register and then mislead."""

    def test_registration_returns_the_class_so_it_works_as_a_decorator(self):
        self.assertIs(HandlerRegistry.register_handler(SchemaOnlyHandler), SchemaOnlyHandler)
        self.assertIs(HandlerRegistry.get_handler('CUSTOM'), SchemaOnlyHandler)

    def test_registering_the_same_class_twice_is_harmless(self):
        HandlerRegistry.register_handler(SchemaOnlyHandler)
        HandlerRegistry.register_handler(SchemaOnlyHandler)

        self.assertIs(HandlerRegistry.get_handler('CUSTOM'), SchemaOnlyHandler)

    def test_a_non_handler_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'not a BaseSensorHandler'):
            HandlerRegistry.register_handler(dict)

    def test_an_abstract_handler_is_refused(self):
        class NoProcessing(BaseSensorHandler):
            SENSOR_TYPES = ['CUSTOM']

            @classmethod
            def get_reading_schema(cls):
                return {'type': 'object'}

        with self.assertRaisesMessage(ImproperlyConfigured, 'process_reading'):
            HandlerRegistry.register_handler(NoProcessing)

    def test_a_handler_with_no_types_is_refused(self):
        class Typeless(SchemaOnlyHandler):
            SENSOR_TYPES = []

        with self.assertRaisesMessage(ImproperlyConfigured, 'no SENSOR_TYPES'):
            HandlerRegistry.register_handler(Typeless)

    def test_a_type_the_model_cannot_hold_is_refused(self):
        """Almost always a typo — and silent without this, since a handler for
        a type no sensor can have simply never runs."""
        class Typo(SchemaOnlyHandler):
            SENSOR_TYPES = ['SMOKE_DETECTOR']

        with self.assertRaisesMessage(ImproperlyConfigured, "['SMOKE_DETECTOR']"):
            HandlerRegistry.register_handler(Typo)

    def test_two_handlers_cannot_claim_one_type(self):
        """Ambiguous dispatch: whichever won, the other's detection would
        silently never run."""
        class Rival(SchemaOnlyHandler):
            SENSOR_TYPES = ['DOOR_CONTACT']

        with self.assertRaisesMessage(ImproperlyConfigured, 'claimed by both'):
            HandlerRegistry.register_handler(Rival)

        self.assertIs(HandlerRegistry.get_handler('DOOR_CONTACT'), ContactHandler)

    def test_a_handler_that_validates_nothing_is_refused(self):
        """No schema and the default validate_reading would accept anything."""
        class Permissive(BaseSensorHandler):
            SENSOR_TYPES = ['CUSTOM']

            def process_reading(self, data):
                return data

        with self.assertRaisesMessage(ImproperlyConfigured, 'validates nothing'):
            HandlerRegistry.register_handler(Permissive)

    def test_overriding_validate_reading_is_enough(self):
        class Imperative(BaseSensorHandler):
            SENSOR_TYPES = ['CUSTOM']

            def validate_reading(self, data):
                return isinstance(data, dict), None

            def process_reading(self, data):
                return data

        HandlerRegistry.register_handler(Imperative)

        self.assertIs(HandlerRegistry.get_handler('CUSTOM'), Imperative)

    def test_a_malformed_schema_is_refused_at_registration(self):
        """At startup, rather than on the first reading that reaches it."""
        class Malformed(SchemaOnlyHandler):
            @classmethod
            def get_reading_schema(cls):
                return {'type': 'not-a-real-type'}

        with self.assertRaisesMessage(ImproperlyConfigured, 'malformed reading schema'):
            HandlerRegistry.register_handler(Malformed)

    def test_unregistering_removes_every_type(self):
        HandlerRegistry.unregister_handler(ContactHandler)

        self.assertIsNone(HandlerRegistry.get_handler('DOOR_CONTACT'))
        self.assertIsNone(HandlerRegistry.get_handler('WINDOW_CONTACT'))


class EntryPointTests(RegistryTestCase):
    class FakeEntryPoint:
        def __init__(self, name, target):
            self.name, self.value, self._target = name, 'pkg.mod:Handler', target

        def load(self):
            if isinstance(self._target, Exception):
                raise self._target
            return self._target

    def test_an_installed_plugin_is_registered(self):
        ep = self.FakeEntryPoint('acme_custom', SchemaOnlyHandler)

        with patch('sensors.registry.entry_points', return_value=[ep]) as found:
            HandlerRegistry.autodiscover()

        found.assert_called_with(group=ENTRY_POINT_GROUP)
        self.assertIs(HandlerRegistry.get_handler('CUSTOM'), SchemaOnlyHandler)

    def test_a_plugin_that_fails_to_load_stops_startup_and_says_which(self):
        ep = self.FakeEntryPoint('broken', ImportError('No module named acme'))

        with patch('sensors.registry.entry_points', return_value=[ep]):
            with self.assertRaisesMessage(ImproperlyConfigured, "'broken'"):
                HandlerRegistry.autodiscover()


class SchemaValidationTests(TestCase):
    """The default validate_reading, driven by get_reading_schema()."""

    def setUp(self):
        owner = User.objects.create_user(username='o', password='x' * 12)
        self.handler = SchemaOnlyHandler(Sensor(
            name='Gauge', sensor_type='CUSTOM', location='Lab', owner=owner,
        ))

    def test_a_valid_reading_passes(self):
        self.assertEqual(self.handler.validate_reading({'level': 3}), (True, None))

    def test_an_invalid_reading_names_the_path(self):
        is_valid, error = self.handler.validate_reading({'level': 99})

        self.assertFalse(is_valid)
        self.assertIn('$.level', error)

    def test_every_problem_is_reported_at_once(self):
        is_valid, error = self.handler.validate_reading({'level': 'high', 'x': 1})

        self.assertFalse(is_valid)
        self.assertIn('$.level', error)

    def test_a_handler_without_a_schema_reports_no_errors(self):
        self.assertEqual(schema_errors(ContactHandler, 'connection', {'any': 'thing'}), [])


@override_settings(CACHES=TEST_CACHES)
class RegistryDispatchTests(RegistryTestCase):
    """Ingest and alerting both go through the registry, not a hardcoded map."""

    def setUp(self):
        super().setUp()
        cache.clear()
        HandlerRegistry.register_handler(SchemaOnlyHandler)
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='x' * 12)
        self.client.force_authenticate(user=self.owner)
        self.sensor = Sensor.objects.create(
            name='Gauge', sensor_type='CUSTOM', location='Lab', owner=self.owner,
            connection_config={'device_id': 'g-1'},
        )

    def post(self, value):
        return self.client.post(
            f'/api/sensors/{self.sensor.pk}/readings/',
            {'value': value, 'reading_type': 'level'}, format='json',
        )

    def test_a_registered_handler_validates_ingest(self):
        response = self.post({'level': 99})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_a_registered_handler_raises_alerts(self):
        self.post({'level': 9})

        self.assertEqual(Alert.objects.get().severity, 'HIGH')

    def test_unregistering_falls_back_to_the_generic_path(self):
        HandlerRegistry.unregister_handler(SchemaOnlyHandler)

        response = self.post({'anything': 'goes'})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Alert.objects.count(), 0)


@override_settings(CACHES=TEST_CACHES)
class ConnectionSchemaTests(RegistryTestCase):
    """get_connection_schema(), applied by SensorSerializer per sensor type."""

    def setUp(self):
        super().setUp()
        cache.clear()
        HandlerRegistry.register_handler(SchemaOnlyHandler)
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='x' * 12)
        self.client.force_authenticate(user=self.owner)

    def create(self, **config):
        return self.client.post('/api/sensors/', {
            'name': 'Gauge', 'sensor_type': 'CUSTOM', 'location': 'Lab',
            'connection_config': config,
        }, format='json')

    def test_a_config_failing_the_types_schema_is_refused(self):
        response = self.create(port=80)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('device_id', str(response.data['connection_config']))

    def test_a_conforming_config_is_accepted(self):
        self.assertEqual(self.create(device_id='g-1').status_code, status.HTTP_201_CREATED)

    def test_types_without_a_connection_schema_are_unaffected(self):
        response = self.client.post('/api/sensors/', {
            'name': 'Door', 'sensor_type': 'DOOR_CONTACT', 'location': 'Front',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_an_unrelated_edit_does_not_revalidate_a_stored_config(self):
        """A config stored before the schema existed must not make renaming
        the sensor fail. Field validators do not re-validate old rows either."""
        legacy = Sensor.objects.create(
            name='Old', sensor_type='CUSTOM', location='Lab', owner=self.owner,
            connection_config={},
        )

        response = self.client.patch(
            f'/api/sensors/{legacy.pk}/', {'name': 'Renamed'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_changing_type_checks_the_config_against_the_new_type(self):
        door = Sensor.objects.create(
            name='Door', sensor_type='DOOR_CONTACT', location='Front', owner=self.owner,
        )

        response = self.client.patch(
            f'/api/sensors/{door.pk}/', {'sensor_type': 'CUSTOM'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
