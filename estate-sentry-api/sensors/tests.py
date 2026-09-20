"""Sensor ingest behaviour.

Currently scoped to the reading rate limit. The handler framework and threat
detection are still uncovered; that is tracked separately in docs/Todo.md under
Milestone 10.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User

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
