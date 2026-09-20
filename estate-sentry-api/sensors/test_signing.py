"""Reading signatures.

Weighted towards the ways a signature scheme fails in practice rather than the
happy path: replay, substitution across sensors, tampering that leaves the
signature syntactically fine, and the denial-of-service you get by burning a
nonce before you have earned the right to.
"""

import base64
from datetime import UTC, datetime, timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from authentication.models import User

from .models import Sensor, SensorReading
from .signing import (
    MAX_CLOCK_SKEW,
    SignatureError,
    canonical_bytes,
    enforce_policy,
    load_public_key,
)

TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'estate-sentry-tests',
    }
}


def _keypair():
    private_key = ed25519.Ed25519PrivateKey.generate()
    encoded = base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode()
    return private_key, encoded


def _now():
    return datetime.now(UTC).isoformat()


@override_settings(CACHES=TEST_CACHES)
class SigningTestCase(TestCase):
    def setUp(self):
        # Nonces live in the cache, so a stale one would leak between tests.
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='x' * 12)
        self.client.force_authenticate(user=self.owner)
        self.private_key, self.public_key = _keypair()
        self.sensor = Sensor.objects.create(
            name='Front Door', sensor_type='DOOR_CONTACT', location='Front',
            owner=self.owner, public_key=self.public_key, require_signature=True,
        )

    def sign(self, value, nonce='n-1', signed_at=None, private_key=None, sensor=None):
        signed_at = signed_at or _now()
        key = private_key or self.private_key
        target = sensor or self.sensor
        signature = key.sign(canonical_bytes(target.pk, nonce, signed_at, value))
        return base64.b64encode(signature).decode(), nonce, signed_at

    def post(self, value, signature=None, nonce=None, signed_at=None, sensor=None):
        target = sensor or self.sensor
        body = {'value': value, 'reading_type': 'state'}
        if nonce is not None:
            body['nonce'] = nonce
        if signed_at is not None:
            body['signed_at'] = signed_at
        kwargs = {}
        if signature is not None:
            kwargs['HTTP_X_SENSOR_SIGNATURE'] = signature
        return self.client.post(
            f'/api/sensors/{target.pk}/readings/', body, format='json', **kwargs
        )


class CanonicalFormTests(TestCase):
    """The wire contract. A producer must reproduce these bytes exactly."""

    def test_keys_are_sorted_and_separators_are_compact(self):
        self.assertEqual(
            canonical_bytes(7, 'abc', '2026-01-01T00:00:00+00:00', {'b': 1, 'a': 2}),
            b'{"nonce":"abc","sensor_id":7,"signed_at":"2026-01-01T00:00:00+00:00",'
            b'"value":{"a":2,"b":1}}',
        )

    def test_value_key_order_does_not_change_the_bytes(self):
        """Otherwise two encoders of the same reading would disagree."""
        self.assertEqual(
            canonical_bytes(1, 'n', 't', {'a': 1, 'b': 2}),
            canonical_bytes(1, 'n', 't', {'b': 2, 'a': 1}),
        )

    def test_the_sensor_is_inside_the_signed_payload(self):
        """So a captured signature cannot be replayed at a different sensor."""
        self.assertNotEqual(
            canonical_bytes(1, 'n', 't', {'state': 'open'}),
            canonical_bytes(2, 'n', 't', {'state': 'open'}),
        )


class PublicKeyLoadingTests(TestCase):
    def test_a_valid_key_loads(self):
        _, encoded = _keypair()

        self.assertIsNotNone(load_public_key(encoded))

    def test_non_base64_is_refused(self):
        with self.assertRaises(SignatureError):
            load_public_key('not base64 at all!!')

    def test_a_key_of_the_wrong_length_is_refused(self):
        with self.assertRaises(SignatureError) as ctx:
            load_public_key(base64.b64encode(b'too short').decode())

        self.assertIn('Ed25519 key is 32', ctx.exception.args[0])


class SignedIngestTests(SigningTestCase):
    def test_a_correctly_signed_reading_is_accepted(self):
        signature, nonce, signed_at = self.sign({'state': 'closed'})

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SensorReading.objects.count(), 1)

    def test_the_signature_fields_are_not_stored_on_the_reading(self):
        """They authenticate the reading; they are not part of it."""
        signature, nonce, signed_at = self.sign({'state': 'closed'})

        self.post({'state': 'closed'}, signature, nonce, signed_at)

        stored = SensorReading.objects.get().value
        self.assertNotIn('nonce', stored)
        self.assertNotIn('signed_at', stored)

    def test_a_tampered_value_is_refused(self):
        """The signature is syntactically fine; it just is not for this body."""
        signature, nonce, signed_at = self.sign({'state': 'closed'})

        response = self.post({'state': 'open'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_another_sensors_key_is_refused(self):
        other_key, _ = _keypair()
        signature, nonce, signed_at = self.sign(
            {'state': 'closed'}, private_key=other_key
        )

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_signature_for_a_different_sensor_is_refused(self):
        """Same key, same body, wrong sensor — `sensor_id` is inside the
        payload precisely so this fails."""
        twin = Sensor.objects.create(
            name='Back Door', sensor_type='DOOR_CONTACT', location='Back',
            owner=self.owner, public_key=self.public_key, require_signature=True,
        )
        signature, nonce, signed_at = self.sign({'state': 'closed'}, sensor=twin)

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_malformed_signature_is_refused(self):
        response = self.post({'state': 'closed'}, 'not base64!!', 'n-1', _now())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReplayTests(SigningTestCase):
    def test_a_replayed_nonce_is_refused(self):
        """A signature alone is a licence to resend a captured reading for
        ever. This is what stops that."""
        signature, nonce, signed_at = self.sign({'state': 'closed'})

        first = self.post({'state': 'closed'}, signature, nonce, signed_at)
        second = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SensorReading.objects.count(), 1)

    def test_a_stale_timestamp_is_refused(self):
        stale = (
            datetime.now(UTC) - MAX_CLOCK_SKEW - timedelta(seconds=30)
        ).isoformat()
        signature, nonce, signed_at = self.sign({'state': 'closed'}, signed_at=stale)

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_timestamp_from_the_future_is_refused(self):
        ahead = (
            datetime.now(UTC) + MAX_CLOCK_SKEW + timedelta(seconds=30)
        ).isoformat()
        signature, nonce, signed_at = self.sign({'state': 'closed'}, signed_at=ahead)

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_naive_timestamp_is_refused(self):
        """Without an offset there is no way to know what window it is in."""
        naive = datetime.now().replace(tzinfo=None).isoformat()
        signature, nonce, signed_at = self.sign({'state': 'closed'}, signed_at=naive)

        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_failed_verification_does_not_burn_the_nonce(self):
        """Otherwise anyone who can reach the endpoint could deny this sensor
        by spending the nonces it was about to use."""
        signature, nonce, signed_at = self.sign({'state': 'closed'})

        # An attacker guesses the nonce and sends rubbish under it.
        self.post({'state': 'closed'}, 'AAAA', nonce, signed_at)

        # The real reading still goes through.
        response = self.post({'state': 'closed'}, signature, nonce, signed_at)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_missing_nonce_is_refused(self):
        signature, _, signed_at = self.sign({'state': 'closed'})

        response = self.post({'state': 'closed'}, signature, None, signed_at)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PolicyTests(SigningTestCase):
    """The four states, which together make a staged rollout possible."""

    def test_a_keyless_sensor_accepts_unsigned_readings(self):
        """How every sensor starts; enabling signing must not be a flag day."""
        legacy = Sensor.objects.create(
            name='Old Door', sensor_type='DOOR_CONTACT', location='Side',
            owner=self.owner,
        )

        response = self.post({'state': 'closed'}, sensor=legacy)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_keyed_sensor_not_yet_enforcing_accepts_unsigned(self):
        """Rollout mode: the key is installed, the device is not signing yet."""
        self.sensor.require_signature = False
        self.sensor.save(update_fields=['require_signature'])

        response = self.post({'state': 'closed'})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_keyed_sensor_not_yet_enforcing_still_checks_a_bad_signature(self):
        """Verified when present, even before it is required — otherwise
        rollout mode would silently accept forgeries."""
        self.sensor.require_signature = False
        self.sensor.save(update_fields=['require_signature'])

        response = self.post({'state': 'closed'}, 'AAAA', 'n-1', _now())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_enforcing_sensor_refuses_an_unsigned_reading(self):
        response = self.post({'state': 'closed'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requiring_signatures_without_a_key_fails_closed(self):
        """A misconfiguration that could silently accept everything instead
        refuses everything."""
        misconfigured = Sensor.objects.create(
            name='Broken', sensor_type='DOOR_CONTACT', location='Nowhere',
            owner=self.owner, require_signature=True,
        )

        with self.assertRaises(SignatureError):
            enforce_policy(misconfigured, '', '', '', {'state': 'closed'})


class KeyIsNotSettableOverTheApiTests(SigningTestCase):
    """A key the account token can rotate is a key it can forge around."""

    def test_creating_a_sensor_cannot_set_a_public_key(self):
        _, attacker_key = _keypair()

        self.client.post('/api/sensors/', {
            'name': 'Mine', 'sensor_type': 'DOOR_CONTACT', 'location': 'Front',
            'public_key': attacker_key, 'require_signature': True,
        }, format='json')

        self.assertEqual(Sensor.objects.get(name='Mine').public_key, '')

    def test_updating_a_sensor_cannot_replace_its_public_key(self):
        _, attacker_key = _keypair()

        self.client.patch(
            f'/api/sensors/{self.sensor.pk}/',
            {'public_key': attacker_key}, format='json',
        )

        self.sensor.refresh_from_db()
        self.assertEqual(self.sensor.public_key, self.public_key)

    def test_enforcement_cannot_be_switched_off_over_the_api(self):
        self.client.patch(
            f'/api/sensors/{self.sensor.pk}/',
            {'require_signature': False}, format='json',
        )

        self.sensor.refresh_from_db()
        self.assertTrue(self.sensor.require_signature)

    def test_the_public_key_is_visible(self):
        """Readable is fine — it is a public key."""
        response = self.client.get(f'/api/sensors/{self.sensor.pk}/')

        self.assertEqual(response.data['public_key'], self.public_key)


class EnrolSensorKeyCommandTests(SigningTestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('enroll_sensor_key', *args, stdout=out)
        return out.getvalue()

    def test_it_generates_a_working_keypair(self):
        sensor = Sensor.objects.create(
            name='Fresh', sensor_type='DOOR_CONTACT', location='Front',
            owner=self.owner,
        )

        output = self._run(str(sensor.pk))

        sensor.refresh_from_db()
        self.assertNotEqual(sensor.public_key, '')
        self.assertIn('private key:', output)

        # The printed private key must actually verify against the stored one.
        secret = [
            line.split('private key:')[1].strip()
            for line in output.splitlines() if 'private key:' in line
        ][0]
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(secret)
        )
        signature, nonce, signed_at = self.sign(
            {'state': 'closed'}, private_key=private_key, sensor=sensor
        )
        response = self.post({'state': 'closed'}, signature, nonce, signed_at,
                             sensor=sensor)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_it_accepts_a_device_supplied_public_key(self):
        """Preferred where the hardware can keep a secret: the private key then
        never exists anywhere but on the device."""
        sensor = Sensor.objects.create(
            name='Fresh', sensor_type='DOOR_CONTACT', location='Front',
            owner=self.owner,
        )
        _, encoded = _keypair()

        output = self._run(str(sensor.pk), '--public-key', encoded)

        sensor.refresh_from_db()
        self.assertEqual(sensor.public_key, encoded)
        self.assertNotIn('private key:', output)

    def test_a_malformed_public_key_is_refused(self):
        with self.assertRaises(CommandError):
            self._run(str(self.sensor.pk), '--public-key', 'nonsense!!')

    def test_an_unknown_sensor_is_an_error(self):
        with self.assertRaises(CommandError):
            self._run('99999')

    def test_require_only_needs_an_enrolled_key(self):
        """Turning on enforcement without a key would refuse every reading."""
        keyless = Sensor.objects.create(
            name='Keyless', sensor_type='DOOR_CONTACT', location='Front',
            owner=self.owner,
        )

        with self.assertRaises(CommandError):
            self._run(str(keyless.pk), '--require-only')

    def test_require_only_turns_enforcement_on(self):
        self.sensor.require_signature = False
        self.sensor.save(update_fields=['require_signature'])

        self._run(str(self.sensor.pk), '--require-only')

        self.sensor.refresh_from_db()
        self.assertTrue(self.sensor.require_signature)

    def test_it_warns_when_replacing_a_key(self):
        output = self._run(str(self.sensor.pk))

        self.assertIn('previous key no longer verifies', output)
