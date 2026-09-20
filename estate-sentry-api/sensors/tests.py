"""Sensor ingest behaviour.

Currently scoped to the reading rate limit. The handler framework and threat
detection are still uncovered; that is tracked separately in docs/Todo.md under
Milestone 10.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from alerts.models import Alert
from authentication.models import User

from .handlers.camera import CameraHandler
from .handlers.contact import ContactHandler
from .models import Sensor, SensorReading

# One above the configured 60/min, so a loop of this length must cross it.
OVER_THE_LIMIT = 65

# 'closed' rather than 'open': a valid reading that does not also trip the
# intrusion alert, keeping these tests about the throttle and nothing else.
READING = {'value': {'state': 'closed'}, 'reading_type': 'state'}


# Throttle tests count on a cache they exclusively own. Pinned to LocMemCache so
# the suite neither depends on a running Redis nor flushes a developer's real one
# when REDIS_URL happens to be set in the environment.
TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'estate-sentry-tests',
    }
}


@override_settings(CACHES=TEST_CACHES)
class SensorTestCase(TestCase):
    """Base that clears the throttle state between tests.

    DRF keeps rate-limit counters in the cache, which outlives a test. Without
    this, tests interfere with each other in a way that depends on execution
    order — and the first symptom is unrelated tests failing with 429.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='x' * 12)
        self.client.force_authenticate(user=self.owner)

    def make_sensor(self, owner=None, name='Front Door'):
        return Sensor.objects.create(
            name=name,
            sensor_type='DOOR_CONTACT',
            location='Front',
            owner=owner or self.owner,
        )

    def post_reading(self, sensor, client=None):
        return (client or self.client).post(
            f'/api/sensors/{sensor.pk}/readings/', READING, format='json'
        )


class ReadingThrottleTests(SensorTestCase):
    """The per-sensor ingest limit."""

    def test_a_reading_is_accepted_under_the_limit(self):
        sensor = self.make_sensor()

        response = self.post_reading(sensor)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SensorReading.objects.count(), 1)

    def test_sustained_posting_is_throttled(self):
        sensor = self.make_sensor()

        codes = [self.post_reading(sensor).status_code for _ in range(OVER_THE_LIMIT)]

        self.assertIn(
            status.HTTP_429_TOO_MANY_REQUESTS, codes,
            'a sensor posting faster than its limit should be throttled',
        )

    def test_a_throttled_reading_is_not_stored(self):
        """429 has to mean the row was refused, not merely reported late."""
        sensor = self.make_sensor()

        for _ in range(OVER_THE_LIMIT):
            self.post_reading(sensor)

        self.assertLessEqual(SensorReading.objects.count(), 60)


class ThrottleIsPerSensorTests(SensorTestCase):
    """The property that a per-account throttle would not have.

    `ScopedRateThrottle` keys on the user, so every sensor on an estate would
    have drawn from one budget and a single chatty device could have silenced
    the rest.
    """

    def test_exhausting_one_sensor_leaves_another_alone(self):
        noisy = self.make_sensor(name='Noisy Camera')
        quiet = self.make_sensor(name='Back Door')

        for _ in range(OVER_THE_LIMIT):
            self.post_reading(noisy)

        response = self.post_reading(quiet)

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED,
            'one sensor exhausting its budget must not silence another',
        )


class ThrottleIsolatesCallersTests(SensorTestCase):
    """A stranger must not be able to spend someone else's budget.

    Throttles are checked before the view body, so ownership — enforced in
    `get_object()` — has not been established yet. Keying on the sensor alone
    would let any authenticated account suppress a stranger's sensor by posting
    to its id and collecting 404s.
    """

    def test_a_stranger_cannot_exhaust_the_owners_budget(self):
        sensor = self.make_sensor()

        stranger = User.objects.create_user(username='stranger', password='x' * 12)
        stranger_client = APIClient()
        stranger_client.force_authenticate(user=stranger)

        codes = [
            self.post_reading(sensor, client=stranger_client).status_code
            for _ in range(OVER_THE_LIMIT)
        ]

        # The stranger is refused throughout — on ownership first, then on their
        # own exhausted bucket — and never writes a row.
        self.assertTrue(set(codes) <= {
            status.HTTP_404_NOT_FOUND, status.HTTP_429_TOO_MANY_REQUESTS,
        }, f'unexpected status codes: {sorted(set(codes))}')
        self.assertEqual(SensorReading.objects.count(), 0)

        # The owner is unaffected.
        response = self.post_reading(sensor)
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED,
            "a stranger's traffic must not consume the owner's budget",
        )


class ReadPathIsNotThrottledTests(SensorTestCase):
    """Only the write path is bounded."""

    def test_history_is_not_throttled_by_ingest_limit(self):
        sensor = self.make_sensor()

        codes = [
            self.client.get(f'/api/sensors/{sensor.pk}/reading_history/').status_code
            for _ in range(OVER_THE_LIMIT)
        ]

        self.assertNotIn(
            status.HTTP_429_TOO_MANY_REQUESTS, codes,
            'reading history is a read and should not draw on the ingest budget',
        )


class ContactHandlerTests(SensorTestCase):
    """`ContactHandler` — door and window contacts."""

    def setUp(self):
        super().setUp()
        self.sensor = self.make_sensor()
        self.handler = ContactHandler(self.sensor)

    def test_a_valid_reading_passes(self):
        for state in ('open', 'closed'):
            with self.subTest(state=state):
                self.assertEqual(
                    self.handler.validate_reading({'state': state}), (True, None)
                )

    def test_a_non_dict_is_refused(self):
        is_valid, error = self.handler.validate_reading(['open'])

        self.assertFalse(is_valid)
        self.assertIn('dictionary', error)

    def test_a_missing_state_is_refused(self):
        is_valid, error = self.handler.validate_reading({'battery_level': 90})

        self.assertFalse(is_valid)
        self.assertIn('state', error)

    def test_a_state_outside_the_vocabulary_is_refused(self):
        """'ajar' is the kind of thing a third-party device sends."""
        is_valid, error = self.handler.validate_reading({'state': 'ajar'})

        self.assertFalse(is_valid)
        self.assertIn("'open' or 'closed'", error)

    def test_processing_renames_battery_level(self):
        """The wire calls it `battery_level`; storage calls it
        `sensor_battery`. The rename is the point of processing."""
        processed = self.handler.process_reading(
            {'state': 'open', 'battery_level': 80, 'timestamp': '2026-01-01T00:00:00Z'}
        )

        self.assertEqual(processed['sensor_battery'], 80)
        self.assertEqual(processed['state'], 'open')
        self.assertEqual(processed['timestamp'], '2026-01-01T00:00:00Z')
        self.assertNotIn('battery_level', processed)

    def test_processing_tolerates_the_optional_fields_being_absent(self):
        processed = self.handler.process_reading({'state': 'closed'})

        self.assertIsNone(processed['sensor_battery'])
        self.assertIsNone(processed['timestamp'])

    def test_an_open_contact_raises_one_medium_alert(self):
        reading = SensorReading.objects.create(
            sensor=self.sensor, value={'state': 'open'}, reading_type='state'
        )

        alerts = self.handler.detect_threats(reading)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['severity'], 'MEDIUM')
        self.assertEqual(alerts[0]['metadata']['reading_id'], reading.id)

    def test_a_closed_contact_raises_nothing(self):
        reading = SensorReading.objects.create(
            sensor=self.sensor, value={'state': 'closed'}, reading_type='state'
        )

        self.assertEqual(self.handler.detect_threats(reading), [])

    def test_the_alert_type_follows_the_sensor_type(self):
        """One handler serves both contact types, so the door/window
        distinction lives in the alert it produces, not in the class."""
        cases = {'DOOR_CONTACT': 'DOOR_OPEN', 'WINDOW_CONTACT': 'WINDOW_OPEN'}

        for sensor_type, expected in cases.items():
            with self.subTest(sensor_type=sensor_type):
                sensor = Sensor.objects.create(
                    name=sensor_type, sensor_type=sensor_type,
                    location='Somewhere', owner=self.owner,
                )
                reading = SensorReading.objects.create(
                    sensor=sensor, value={'state': 'open'}, reading_type='state'
                )

                alerts = ContactHandler(sensor).detect_threats(reading)

                self.assertEqual(alerts[0]['alert_type'], expected)


class CameraHandlerTests(SensorTestCase):
    """`CameraHandler` — a skeleton until single-shot recognition lands."""

    def setUp(self):
        super().setUp()
        self.sensor = Sensor.objects.create(
            name='Drive Cam', sensor_type='CAMERA',
            location='Driveway', owner=self.owner,
        )
        self.handler = CameraHandler(self.sensor)

    def test_either_field_is_enough(self):
        for data in ({'image_url': 'https://example.test/f.jpg'},
                     {'motion_detected': True}):
            with self.subTest(data=data):
                self.assertEqual(self.handler.validate_reading(data), (True, None))

    def test_neither_field_is_refused(self):
        is_valid, error = self.handler.validate_reading({'temperature': 20})

        self.assertFalse(is_valid)
        self.assertIn('image_url', error)

    def test_motion_defaults_to_false_when_absent(self):
        processed = self.handler.process_reading(
            {'image_url': 'https://example.test/f.jpg'}
        )

        self.assertIs(processed['motion_detected'], False)

    def test_motion_raises_a_low_alert(self):
        reading = SensorReading.objects.create(
            sensor=self.sensor,
            value={'motion_detected': True, 'image_url': 'https://example.test/f.jpg'},
            reading_type='frame',
        )

        alerts = self.handler.detect_threats(reading)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alert_type'], 'MOTION')
        self.assertEqual(alerts[0]['severity'], 'LOW')
        self.assertEqual(
            alerts[0]['metadata']['image_url'], 'https://example.test/f.jpg'
        )

    def test_stillness_raises_nothing(self):
        reading = SensorReading.objects.create(
            sensor=self.sensor, value={'motion_detected': False}, reading_type='frame'
        )

        self.assertEqual(self.handler.detect_threats(reading), [])


class IngestPipelineTests(SensorTestCase):
    """POST /api/sensors/{id}/readings/ end to end.

    The path `CLAUDE.md` documents as the core runtime flow: serializer picks a
    handler, handler validates and normalises, the row is written, threats
    become alerts, the row is marked processed.
    """

    def test_the_stored_value_is_processed_not_raw(self):
        """The whole point of the handler round trip. If this regresses,
        readings silently keep their wire shape."""
        sensor = self.make_sensor()

        self.client.post(
            f'/api/sensors/{sensor.pk}/readings/',
            {'value': {'state': 'open', 'battery_level': 55}, 'reading_type': 'state'},
            format='json',
        )

        reading = SensorReading.objects.get()
        self.assertEqual(reading.value['sensor_battery'], 55)
        self.assertNotIn('battery_level', reading.value)

    def test_an_invalid_reading_is_a_400_and_writes_nothing(self):
        sensor = self.make_sensor()

        response = self.client.post(
            f'/api/sensors/{sensor.pk}/readings/',
            {'value': {'state': 'ajar'}, 'reading_type': 'state'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_a_threat_reading_creates_an_alert(self):
        sensor = self.make_sensor()

        self.client.post(
            f'/api/sensors/{sensor.pk}/readings/',
            {'value': {'state': 'open'}, 'reading_type': 'state'},
            format='json',
        )

        alert = Alert.objects.get()
        self.assertEqual(alert.alert_type, 'DOOR_OPEN')
        self.assertEqual(alert.severity, 'MEDIUM')
        self.assertEqual(alert.sensor, sensor)
        self.assertEqual(
            alert.user, self.owner,
            'the alert belongs to the sensor owner, not whoever posted it',
        )

    def test_a_benign_reading_creates_no_alert(self):
        sensor = self.make_sensor()

        self.post_reading(sensor)  # state: closed

        self.assertEqual(SensorReading.objects.count(), 1)
        self.assertEqual(Alert.objects.count(), 0)

    def test_the_reading_is_marked_processed(self):
        sensor = self.make_sensor()

        self.post_reading(sensor)

        self.assertTrue(SensorReading.objects.get().processed)

    def test_posting_to_another_owners_sensor_is_a_404(self):
        stranger = User.objects.create_user(username='other', password='x' * 12)
        their_sensor = self.make_sensor(owner=stranger, name='Their Door')

        response = self.post_reading(their_sensor)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_reading_history_is_scoped_to_the_owner(self):
        stranger = User.objects.create_user(username='other', password='x' * 12)
        their_sensor = self.make_sensor(owner=stranger, name='Their Door')
        SensorReading.objects.create(
            sensor=their_sensor, value={'state': 'open'}, reading_type='state'
        )

        response = self.client.get(
            f'/api/sensors/{their_sensor.pk}/reading_history/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UnhandledSensorTypeTests(SensorTestCase):
    """Seven of the ten sensor types have no handler.

    `GLASS_BREAK`, `MOTION`, `SMOKE`, `CO`, `WATER_LEAK`, `TEMPERATURE` and
    `CUSTOM` are absent from the handler map in `sensors/serializers.py`, so
    `validate()` falls through and stores whatever arrives, unchecked and
    unnormalised.

    These tests pin the behaviour as it is today rather than endorse it. It is
    the gap JSON Schema validation closes — `docs/Todo.md`, Milestone 1 — and
    the handler registry after that. Expect them to change then.
    """

    UNHANDLED = [
        'GLASS_BREAK', 'MOTION', 'SMOKE', 'CO',
        'WATER_LEAK', 'TEMPERATURE', 'CUSTOM',
    ]

    def test_arbitrary_json_is_accepted_for_types_without_a_handler(self):
        for sensor_type in self.UNHANDLED:
            with self.subTest(sensor_type=sensor_type):
                sensor = Sensor.objects.create(
                    name=sensor_type, sensor_type=sensor_type,
                    location='Somewhere', owner=self.owner,
                )

                response = self.client.post(
                    f'/api/sensors/{sensor.pk}/readings/',
                    {'value': {'utterly': ['un', 'related']}, 'reading_type': 'x'},
                    format='json',
                )

                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED,
                    f'{sensor_type} has no handler, so nothing rejects this',
                )

    def test_the_value_is_stored_unnormalised(self):
        sensor = Sensor.objects.create(
            name='Hall PIR', sensor_type='MOTION',
            location='Hall', owner=self.owner,
        )

        self.client.post(
            f'/api/sensors/{sensor.pk}/readings/',
            {'value': {'raw': 1}, 'reading_type': 'x'},
            format='json',
        )

        self.assertEqual(SensorReading.objects.get().value, {'raw': 1})

    def test_no_threat_detection_runs(self):
        """No handler means no `detect_threats`, so a smoke detector reporting
        smoke raises nothing at all."""
        sensor = Sensor.objects.create(
            name='Kitchen Smoke', sensor_type='SMOKE',
            location='Kitchen', owner=self.owner,
        )

        self.client.post(
            f'/api/sensors/{sensor.pk}/readings/',
            {'value': {'smoke_detected': True}, 'reading_type': 'state'},
            format='json',
        )

        self.assertEqual(Alert.objects.count(), 0)
