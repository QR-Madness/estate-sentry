"""The audit log and its middleware.

Weighted towards the three things that decide whether this works: that the
allowlist holds (so ingest and streaming are not audited), that the async path
can write at all, and that a failure to audit never takes the request with it.
"""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APIClient

from asgiref.sync import async_to_sync

from authentication.models import TrustedDevice, User
from sensors.models import Sensor

from .middleware import AuditMiddleware, _client_ip, _outcome_for
from .models import AuditLog

TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'estate-sentry-tests',
    }
}


@override_settings(CACHES=TEST_CACHES)
class AuditTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(username='owner', password='x' * 12)


class AuditedActionTests(AuditTestCase):
    """Events that must leave a record."""

    def test_a_successful_login_records_the_actor(self):
        """The request is anonymous while it runs — a token is what it is there
        to obtain — so this only works because the view says who succeeded."""
        response = self.client.post(
            '/api/auth/login/', {'username': 'owner', 'password': 'x' * 12}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, 'LOGIN')
        self.assertEqual(entry.outcome, 'SUCCESS')
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.actor_username, 'owner')

    def test_a_failed_login_records_the_username_that_was_tried(self):
        """The entry an investigator most wants, and the one with no user to
        attach it to."""
        self.client.post(
            '/api/auth/login/', {'username': 'owner', 'password': 'wrong'}
        )

        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, 'LOGIN')
        self.assertEqual(entry.outcome, 'FAILURE')
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_username, 'owner')

    def test_a_login_against_a_missing_account_is_still_recorded(self):
        self.client.post(
            '/api/auth/login/', {'username': 'nobody', 'password': 'x' * 12}
        )

        entry = AuditLog.objects.get()
        self.assertEqual(entry.actor_username, 'nobody')
        self.assertIsNone(entry.actor)

    def test_registration_is_recorded(self):
        self.client.post('/api/auth/register/', {
            'username': 'fresh', 'password': 'x' * 12, 'auth_method': 'password',
        })

        entry = AuditLog.objects.get(action='REGISTER')
        self.assertEqual(entry.actor_username, 'fresh')

    def test_sensor_creation_is_recorded_with_the_authenticated_actor(self):
        """Also pins that DRF propagates the authenticated user onto the
        underlying HttpRequest, which is all the middleware can see."""
        self.client.force_authenticate(user=self.user)

        self.client.post('/api/sensors/', {
            'name': 'Front Door', 'sensor_type': 'DOOR_CONTACT', 'location': 'Front',
        }, format='json')

        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, 'SENSOR_CREATE')
        self.assertEqual(entry.actor, self.user)

    def test_sensor_deletion_is_recorded(self):
        self.client.force_authenticate(user=self.user)
        sensor = Sensor.objects.create(
            name='Front Door', sensor_type='DOOR_CONTACT',
            location='Front', owner=self.user,
        )

        self.client.delete(f'/api/sensors/{sensor.pk}/')

        self.assertEqual(AuditLog.objects.get().action, 'SENSOR_DELETE')

    def test_device_enrolment_and_revocation_are_recorded(self):
        self.client.force_authenticate(user=self.user)

        self.client.post('/api/auth/devices/', {'name': 'Kiosk'}, format='json')
        device = TrustedDevice.objects.get()
        self.client.post(f'/api/auth/devices/{device.id}/revoke/')

        self.assertEqual(
            list(AuditLog.objects.order_by('id').values_list('action', flat=True)),
            ['DEVICE_ENROL', 'DEVICE_REVOKE'],
        )

    def test_the_client_address_and_agent_are_captured(self):
        self.client.post(
            '/api/auth/login/', {'username': 'owner', 'password': 'wrong'},
            HTTP_USER_AGENT='probe/1.0',
        )

        entry = AuditLog.objects.get()
        self.assertEqual(entry.user_agent, 'probe/1.0')
        self.assertIsNotNone(entry.ip_address)


class NotAuditedTests(AuditTestCase):
    """The allowlist exists to keep these out."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.sensor = Sensor.objects.create(
            name='Front Door', sensor_type='DOOR_CONTACT',
            location='Front', owner=self.user,
        )

    def test_reading_ingest_is_not_audited(self):
        """60 a minute per sensor, and `SensorReading` is already the record.
        Auditing it would put a second write on the hot path."""
        for _ in range(5):
            self.client.post(
                f'/api/sensors/{self.sensor.pk}/readings/',
                {'value': {'state': 'closed'}, 'reading_type': 'state'},
                format='json',
            )

        self.assertEqual(AuditLog.objects.count(), 0)

    def test_the_healthcheck_is_not_audited(self):
        """Polled every 30s; it would be most of the log."""
        self.client.get('/api/health/')

        self.assertEqual(AuditLog.objects.count(), 0)

    def test_reads_are_not_audited(self):
        self.client.get('/api/sensors/')
        self.client.get('/api/alerts/')
        self.client.get(f'/api/sensors/{self.sensor.pk}/reading_history/')

        self.assertEqual(AuditLog.objects.count(), 0)

    def test_an_unresolved_route_is_not_audited(self):
        self.client.post('/api/nothing-here/', {}, format='json')

        self.assertEqual(AuditLog.objects.count(), 0)


class AsyncPathTests(AuditTestCase):
    """The middleware under ASGI.

    The project serves long-lived MJPEG and SSE responses from async views. An
    async middleware touching the ORM directly raises `SynchronousOnlyOperation`,
    so these exercise `__acall__` rather than trusting that it works.

    Driven with `async_to_sync` from a sync test so the `thread_sensitive` hop
    lands back on this thread, inside the test transaction.
    """

    def _request(self, path, method='post'):
        request = getattr(RequestFactory(), method)(path)
        request.resolver_match = resolve(path)
        request.user = AnonymousUser()
        return request

    def test_an_audited_route_writes_from_the_async_path(self):
        async def get_response(request):
            return HttpResponse(status=200)

        middleware = AuditMiddleware(get_response)
        self.assertTrue(middleware._is_async, 'should have taken the async path')

        async_to_sync(middleware)(self._request('/api/auth/login/'))

        self.assertEqual(AuditLog.objects.get().action, 'LOGIN')

    def test_a_streaming_route_writes_nothing_from_the_async_path(self):
        async def get_response(request):
            return HttpResponse(status=200)

        middleware = AuditMiddleware(get_response)

        async_to_sync(middleware)(self._request('/hq/events/stream', method='get'))

        self.assertEqual(AuditLog.objects.count(), 0)

    def test_the_sync_path_is_taken_for_a_sync_get_response(self):
        middleware = AuditMiddleware(lambda request: HttpResponse(status=200))

        self.assertFalse(middleware._is_async)
        middleware(self._request('/api/auth/login/'))

        self.assertEqual(AuditLog.objects.get().action, 'LOGIN')


class AuditFailureIsContainedTests(AuditTestCase):
    """An audit log that takes the service down with it is worse than none."""

    def test_a_failed_write_does_not_fail_the_request(self):
        with patch(
            'audit.middleware.AuditLog.objects.create',
            side_effect=RuntimeError('database on fire'),
        ):
            response = self.client.post(
                '/api/auth/login/', {'username': 'owner', 'password': 'x' * 12}
            )

        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            'the login succeeded; failing to record it must not undo that',
        )
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_the_failure_is_logged(self):
        with patch(
            'audit.middleware.AuditLog.objects.create',
            side_effect=RuntimeError('database on fire'),
        ):
            with self.assertLogs('audit.middleware', level='ERROR') as logs:
                self.client.post(
                    '/api/auth/login/', {'username': 'owner', 'password': 'x' * 12}
                )

        self.assertIn('Failed to write audit entry', logs.output[0])


class AppendOnlyTests(AuditTestCase):
    """It is evidence, written once — the precedent ZoneEvent sets."""

    def _entry(self):
        return AuditLog.objects.create(
            action='LOGIN', outcome='SUCCESS', method='POST',
            path='/api/auth/login/', status_code=200,
        )

    def test_an_entry_cannot_be_modified(self):
        entry = self._entry()
        entry.outcome = 'FAILURE'

        with self.assertRaises(ValueError):
            entry.save()

    def test_an_entry_cannot_be_deleted(self):
        entry = self._entry()

        with self.assertRaises(ValueError):
            entry.delete()

    def test_there_is_no_route_to_the_log(self):
        """It is not exposed over the API at all; reading it is an operator
        task, not a client one."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/audit/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleting_the_actor_keeps_the_entry_and_the_name(self):
        """SET_NULL, plus a denormalised username: removing an account must not
        remove the record of what it did."""
        self.client.post(
            '/api/auth/login/', {'username': 'owner', 'password': 'x' * 12}
        )
        self.user.delete()

        entry = AuditLog.objects.get()
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_username, 'owner')


class HelperTests(TestCase):
    def test_outcome_mapping(self):
        cases = {200: 'SUCCESS', 201: 'SUCCESS', 400: 'FAILURE',
                 401: 'DENIED', 403: 'DENIED', 404: 'FAILURE', 500: 'FAILURE'}
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(_outcome_for(code), expected)

    def test_the_forwarded_header_wins_over_remote_addr(self):
        request = RequestFactory().get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.9, 10.0.0.1'

        self.assertEqual(_client_ip(request), '203.0.113.9')

    def test_remote_addr_is_used_when_there_is_no_proxy(self):
        request = RequestFactory().get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        self.assertEqual(_client_ip(request), '10.0.0.1')


class BulkOperationsAreRefusedTests(AuditTestCase):
    """The gap instance-level guards leave open.

    `QuerySet.update()` and `QuerySet.delete()` go straight to SQL without
    calling `Model.save()` or `Model.delete()`, so without a manager that
    refuses them the log would be append-only only by convention.
    """

    def _entry(self):
        return AuditLog.objects.create(
            action='LOGIN', outcome='SUCCESS', method='POST',
            path='/api/auth/login/', status_code=200,
        )

    def test_bulk_delete_is_refused(self):
        self._entry()

        with self.assertRaises(ValueError):
            AuditLog.objects.all().delete()

        self.assertEqual(AuditLog.objects.count(), 1)

    def test_bulk_update_is_refused(self):
        self._entry()

        with self.assertRaises(ValueError):
            AuditLog.objects.all().update(outcome='FAILURE')

        self.assertEqual(AuditLog.objects.get().outcome, 'SUCCESS')

    def test_cascade_still_nulls_the_actor(self):
        """The deletion collector issues its own UpdateQuery, so SET_NULL must
        keep working despite update() being blocked."""
        self.client.post(
            '/api/auth/login/', {'username': 'owner', 'password': 'x' * 12}
        )
        self.user.delete()

        self.assertIsNone(AuditLog.objects.get().actor)
