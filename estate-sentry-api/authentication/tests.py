"""Authentication behaviour.

Weighted towards the failure modes. The happy paths were already covered and
were never the problem; what needed pinning is that a PIN is never stored in the
clear, that knowing a username is not enough to get a token, and that guessing
is bounded.
"""

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import MAX_FAILED_ATTEMPTS, TrustedDevice, User


class AuthTestCase(TestCase):
    """Base that clears the throttle state between tests.

    DRF keeps rate-limit counters in the cache, which outlives a test. Without
    this, tests interfere with each other in a way that depends on execution
    order — and the first symptom is unrelated tests failing with 429.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()


class AuthenticationTestCase(AuthTestCase):
    """Registration, login and logout."""

    def test_register_user_password_auth(self):
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123',
            'auth_method': 'password',
            'first_name': 'Test',
            'last_name': 'User'
        }

        response = self.client.post('/api/auth/register/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')

        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.auth_method, 'password')

    def test_register_user_pin_auth_stores_only_a_hash(self):
        """The PIN must not survive registration in a readable form."""
        data = {
            'username': 'pinuser',
            'email': 'pin@example.com',
            'auth_method': 'pin',
            'pin': '1234'
        }

        response = self.client.post('/api/auth/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='pinuser')
        self.assertNotEqual(user.pin, '1234')
        self.assertNotIn('1234', user.pin)
        self.assertTrue(user.check_pin('1234'))
        self.assertFalse(user.check_pin('4321'))

    def test_login_with_password(self):
        User.objects.create_user(
            username='logintest', password='testpass123', auth_method='password'
        )
        response = self.client.post(
            '/api/auth/login/', {'username': 'logintest', 'password': 'testpass123'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_with_pin(self):
        user = User.objects.create(username='pinlogin', auth_method='pin')
        user.set_pin('5678')
        user.save()

        response = self.client.post(
            '/api/auth/login/', {'username': 'pinlogin', 'pin': '5678'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_with_wrong_pin_is_refused(self):
        user = User.objects.create(username='pinlogin', auth_method='pin')
        user.set_pin('5678')
        user.save()

        response = self.client.post(
            '/api/auth/login/', {'username': 'pinlogin', 'pin': '0000'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_credentials(self):
        User.objects.create_user(
            username='testuser', password='correctpass', auth_method='password'
        )
        response = self.client.post(
            '/api/auth/login/', {'username': 'testuser', 'password': 'wrongpass'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_missing_account_and_a_wrong_password_look_identical(self):
        """Otherwise the login endpoint is a username oracle."""
        User.objects.create_user(
            username='real', password='correctpass', auth_method='password'
        )
        wrong = self.client.post(
            '/api/auth/login/', {'username': 'real', 'password': 'nope'}
        )
        missing = self.client.post(
            '/api/auth/login/', {'username': 'ghost', 'password': 'nope'}
        )
        self.assertEqual(wrong.status_code, missing.status_code)
        self.assertEqual(str(wrong.data), str(missing.data))

    def test_logout(self):
        user = User.objects.create_user(
            username='logouttest', password='testpass', auth_method='password'
        )
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PinStorageTests(AuthTestCase):
    def test_set_pin_hashes_and_check_pin_verifies(self):
        user = User.objects.create(username='u', auth_method='pin')
        user.set_pin('4321')
        self.assertNotEqual(user.pin, '4321')
        self.assertTrue(user.check_pin('4321'))
        self.assertFalse(user.check_pin('1234'))

    def test_two_users_with_the_same_pin_get_different_hashes(self):
        """Salted. Otherwise the hashes themselves would reveal which accounts
        share a PIN, and a 10,000-entry rainbow table would cover every user."""
        a = User.objects.create(username='a', auth_method='pin')
        b = User.objects.create(username='b', auth_method='pin')
        a.set_pin('1111')
        b.set_pin('1111')
        self.assertNotEqual(a.pin, b.pin)

    def test_clearing_a_pin(self):
        user = User.objects.create(username='u', auth_method='pin')
        user.set_pin('1234')
        user.set_pin(None)
        self.assertIsNone(user.pin)
        self.assertFalse(user.check_pin('1234'))
        self.assertFalse(user.has_usable_pin())

    def test_check_pin_on_an_account_without_one(self):
        user = User.objects.create(username='u', auth_method='password')
        self.assertFalse(user.check_pin('1234'))
        self.assertFalse(user.check_pin(None))


class TrustedDeviceLoginTests(AuthTestCase):
    """The username-only path.

    Previously this granted a token to anyone who could name an account. A
    username is an identifier, not a secret, so that was not authentication.
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create(username='kiosk', auth_method='username')

    def test_a_username_alone_no_longer_authenticates(self):
        response = self.client.post('/api/auth/login/', {'username': 'kiosk'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_succeeds_with_an_enrolled_device_token(self):
        _, raw = TrustedDevice.issue(self.user, 'Hall tablet')
        response = self.client.post(
            '/api/auth/login/', {'username': 'kiosk', 'device_token': raw}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_the_token_may_arrive_as_a_header(self):
        """So a kiosk can hold it out of band rather than in a form body."""
        _, raw = TrustedDevice.issue(self.user, 'Hall tablet')
        response = self.client.post(
            '/api/auth/login/', {'username': 'kiosk'}, HTTP_X_DEVICE_TOKEN=raw
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_wrong_token_is_refused(self):
        TrustedDevice.issue(self.user, 'Hall tablet')
        response = self.client.post(
            '/api/auth/login/', {'username': 'kiosk', 'device_token': 'not-it'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_users_device_does_not_work(self):
        other = User.objects.create(username='someone-else', auth_method='username')
        _, raw = TrustedDevice.issue(other, 'Their tablet')
        response = self.client.post(
            '/api/auth/login/', {'username': 'kiosk', 'device_token': raw}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_revoked_device_stops_working(self):
        device, raw = TrustedDevice.issue(self.user, 'Lost tablet')
        device.revoke()
        response = self.client.post(
            '/api/auth/login/', {'username': 'kiosk', 'device_token': raw}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TrustedDeviceModelTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create(username='u', auth_method='username')

    def test_the_raw_token_is_not_stored(self):
        device, raw = TrustedDevice.issue(self.user, 'Tablet')
        self.assertNotEqual(device.token_hash, raw)
        self.assertNotIn(raw, device.token_hash)

    def test_each_enrolment_issues_a_distinct_token(self):
        _, first = TrustedDevice.issue(self.user, 'One')
        _, second = TrustedDevice.issue(self.user, 'Two')
        self.assertNotEqual(first, second)
        self.assertGreater(len(first), 30, 'token should be high-entropy')

    def test_authenticating_records_last_seen(self):
        device, raw = TrustedDevice.issue(self.user, 'Tablet')
        self.assertIsNone(device.last_seen_at)
        TrustedDevice.authenticate(self.user, raw)
        device.refresh_from_db()
        self.assertIsNotNone(device.last_seen_at)

    def test_revocation_is_recorded_rather_than_deleted(self):
        """A lost tablet should leave a trace of having been trusted."""
        device, _ = TrustedDevice.issue(self.user, 'Tablet')
        device.revoke()
        self.assertTrue(TrustedDevice.objects.filter(id=device.id).exists())
        self.assertTrue(device.is_revoked)


class TrustedDeviceApiTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='owner', password='x')
        self.client.force_authenticate(self.user)

    def test_enrolment_requires_authentication(self):
        """There must be no path from "knows a username" to "holds a device
        token" — otherwise the hole simply moves."""
        anon = APIClient()
        response = anon.post('/api/auth/devices/', {'name': 'Rogue'})
        self.assertIn(response.status_code, (401, 403))

    def test_enrolment_returns_the_token_once(self):
        response = self.client.post('/api/auth/devices/', {'name': 'Hall tablet'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('device_token', response.data)

        listed = self.client.get('/api/auth/devices/')
        self.assertEqual(listed.data['count'], 1)
        self.assertNotIn('device_token', str(listed.data))
        self.assertNotIn('token_hash', str(listed.data))

    def test_a_device_needs_a_name(self):
        response = self.client.post('/api/auth/devices/', {'name': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_devices_are_scoped_to_their_owner(self):
        other = User.objects.create_user(username='other', password='x')
        TrustedDevice.issue(other, 'Not mine')
        self.assertEqual(self.client.get('/api/auth/devices/').data['count'], 0)

    def test_revoking_someone_elses_device_is_a_404(self):
        other = User.objects.create_user(username='other', password='x')
        device, _ = TrustedDevice.issue(other, 'Not mine')
        response = self.client.post(f'/api/auth/devices/{device.id}/revoke/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        device.refresh_from_db()
        self.assertFalse(device.is_revoked)

    def test_revoking_own_device(self):
        device, _ = TrustedDevice.issue(self.user, 'Mine')
        response = self.client.post(f'/api/auth/devices/{device.id}/revoke/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertTrue(device.is_revoked)


class LockoutTests(AuthTestCase):
    """Bounded guessing.

    A four-digit PIN is 10,000 possibilities. Hashing protects a leaked
    database; it does nothing against someone simply trying every combination
    against the endpoint. The lockout is what makes the PIN mean anything.
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create(username='pinuser', auth_method='pin')
        self.user.set_pin('1234')
        self.user.save()

    def guess(self, pin='0000'):
        return self.client.post(
            '/api/auth/login/', {'username': 'pinuser', 'pin': pin}
        )

    def test_repeated_failures_lock_the_account(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.guess()

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_locked_out)

        # Even the correct PIN is refused while locked.
        self.assertEqual(self.guess('1234').status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_successful_login_clears_the_failure_count(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self.guess()
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_auth_attempts, MAX_FAILED_ATTEMPTS - 1)

        self.assertEqual(self.guess('1234').status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_auth_attempts, 0)
        self.assertIsNone(self.user.locked_until)

    def test_the_lock_expires(self):
        """Finite on purpose: a permanent lock would let anyone who knows a
        username shut the owner out of their own alarm."""
        self.user.failed_auth_attempts = MAX_FAILED_ATTEMPTS
        self.user.locked_until = timezone.now() - timedelta(seconds=1)
        self.user.save()

        self.assertFalse(self.user.is_locked_out)
        self.assertEqual(self.guess('1234').status_code, status.HTTP_200_OK)

    def test_lockout_also_applies_to_password_accounts(self):
        user = User.objects.create_user(
            username='pw', password='correct', auth_method='password'
        )
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post('/api/auth/login/', {'username': 'pw', 'password': 'no'})

        user.refresh_from_db()
        self.assertTrue(user.is_locked_out)


class ThrottleTests(AuthTestCase):
    """The per-client rate limit.

    The account lockout bounds guessing against one account. This bounds one
    client's guessing across many accounts — a lockout alone does nothing
    against someone trying one PIN against a thousand usernames.
    """

    def test_login_is_rate_limited_per_client(self):
        User.objects.create_user(username='u', password='correct')

        codes = [
            self.client.post(
                '/api/auth/login/', {'username': 'u', 'password': 'wrong'}
            ).status_code
            for _ in range(15)
        ]

        self.assertIn(
            status.HTTP_429_TOO_MANY_REQUESTS, codes,
            'sustained guessing from one client should be throttled',
        )

    def test_registration_is_rate_limited(self):
        """Open registration on a security appliance is a questionable default;
        until that is revisited, at least bound how fast accounts appear."""
        codes = []
        for i in range(8):
            codes.append(
                self.client.post('/api/auth/register/', {
                    'username': f'u{i}', 'password': 'x' * 12, 'auth_method': 'password',
                }).status_code
            )
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codes)


class PinMigrationTests(AuthTestCase):
    """The one-way conversion of PINs that were stored in the clear.

    Worth testing directly rather than trusting: it runs once, against real user
    data, and a mistake either locks people out of their own alarm or silently
    leaves plaintext behind.
    """

    @staticmethod
    def load_migration():
        """Load the migration by path.

        Its module name starts with a digit, so it cannot be imported with
        normal syntax.
        """
        import importlib.util
        from pathlib import Path

        path = Path(__file__).parent / "migrations" / "0003_hash_existing_pins.py"
        spec = importlib.util.spec_from_file_location("hash_pins_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    class FakeApps:
        """Stands in for the historical model registry a migration receives."""

        @staticmethod
        def get_model(app_label, model_name):
            return User

    def test_plaintext_is_converted_and_hashes_are_left_alone(self):
        module = self.load_migration()

        plain = User.objects.create(username="legacy", auth_method="pin", pin="4321")
        already = User.objects.create(username="modern", auth_method="pin")
        already.set_pin("9876")
        already.save()
        untouched_hash = already.pin
        no_pin = User.objects.create(username="nopin", auth_method="password")

        module.hash_plaintext_pins(self.FakeApps, None)

        plain.refresh_from_db()
        already.refresh_from_db()
        no_pin.refresh_from_db()

        self.assertNotEqual(plain.pin, "4321", "plaintext must not survive")
        self.assertTrue(plain.check_pin("4321"), "and the PIN must still work")

        self.assertEqual(
            already.pin, untouched_hash, "an existing hash must not be re-hashed"
        )
        self.assertTrue(already.check_pin("9876"))

        self.assertIsNone(no_pin.pin)

    def test_running_it_twice_is_safe(self):
        """Migrations get re-run in restores and re-applied environments. A
        second pass must not hash the hash and lock everyone out."""
        module = self.load_migration()
        user = User.objects.create(username="legacy", auth_method="pin", pin="1111")

        module.hash_plaintext_pins(self.FakeApps, None)
        module.hash_plaintext_pins(self.FakeApps, None)

        user.refresh_from_db()
        self.assertTrue(user.check_pin("1111"))


class EnrollDeviceCommandTests(AuthTestCase):
    """The bootstrap path.

    Without it, `auth_method='username'` is unusable: the account authenticates
    with a device token, so it cannot log in to enrol its first device. Somebody
    has to break that cycle from outside the API.
    """

    def run_command(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("enroll_device", *args, stdout=out)
        return out.getvalue()

    def test_it_enrols_and_prints_a_working_token(self):
        user = User.objects.create(username="kiosk", auth_method="username")
        output = self.run_command("kiosk", "Hall tablet")

        self.assertIn("Hall tablet", output)
        device = TrustedDevice.objects.get(user=user)

        # Recover the token from the output and prove it actually authenticates —
        # printing something token-shaped is not the same as printing the token.
        token = next(
            line.split("device token:")[1].strip()
            for line in output.splitlines()
            if "device token:" in line
        )
        self.assertIsNotNone(TrustedDevice.authenticate(user, token))
        self.assertNotIn(token, device.token_hash)

    def test_an_unknown_user_is_an_error(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.run_command("nobody", "Tablet")

    def test_revoke_existing_replaces_a_lost_device(self):
        user = User.objects.create(username="kiosk", auth_method="username")
        old_device, old_token = TrustedDevice.issue(user, "Lost tablet")

        self.run_command("kiosk", "New tablet", "--revoke-existing")

        old_device.refresh_from_db()
        self.assertTrue(old_device.is_revoked)
        self.assertIsNone(
            TrustedDevice.authenticate(user, old_token),
            "a replaced device must stop working",
        )

    def test_it_warns_when_the_token_will_never_be_used(self):
        """Enrolling against a password account is valid but pointless, and
        silently doing nothing useful is worth saying out loud."""
        User.objects.create_user(username="pw", password="x", auth_method="password")
        output = self.run_command("pw", "Tablet")
        self.assertIn("will not be used", output)
