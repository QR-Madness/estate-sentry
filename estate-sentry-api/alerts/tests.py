"""Alert retrieval and acknowledgement.

Alerts are the output of the whole pipeline, and the viewset is read-only by
design: they are produced by threat detection, never posted by a client. These
tests weight scoping and the acknowledgement flow, since an alert leaking across
accounts or being silently re-acknowledged are the failures that matter on a
security appliance.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from sensors.models import Sensor

from .models import Alert

# Throttle counters outlive a test; pinned to LocMemCache so the suite neither
# depends on a running Redis nor flushes a developer's real one.
TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'estate-sentry-tests',
    }
}


@override_settings(CACHES=TEST_CACHES)
class AlertTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='x' * 12)
        self.client.force_authenticate(user=self.owner)
        self.sensor = Sensor.objects.create(
            name='Front Door', sensor_type='DOOR_CONTACT',
            location='Front', owner=self.owner,
        )

    def make_alert(self, owner=None, severity='MEDIUM', acknowledged=False,
                   alert_type='DOOR_OPEN', title='Front Door Opened'):
        return Alert.objects.create(
            alert_type=alert_type,
            severity=severity,
            sensor=self.sensor,
            user=owner or self.owner,
            title=title,
            description='The front door was opened.',
            acknowledged=acknowledged,
        )


class AlertScopingTests(AlertTestCase):
    """An alert is visible to its owner and to nobody else."""

    def test_own_alerts_are_listed(self):
        self.make_alert()

        response = self.client.get('/api/alerts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_another_users_alerts_are_invisible(self):
        stranger = User.objects.create_user(username='stranger', password='x' * 12)
        self.make_alert(owner=stranger)

        response = self.client.get('/api/alerts/')

        self.assertEqual(response.data['count'], 0)

    def test_another_users_alert_cannot_be_retrieved_directly(self):
        stranger = User.objects.create_user(username='stranger', password='x' * 12)
        theirs = self.make_alert(owner=stranger)

        response = self.client.get(f'/api/alerts/{theirs.pk}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_listing_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/alerts/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AlertFilterTests(AlertTestCase):
    """The `severity` and `acknowledged` query parameters."""

    def test_filtering_by_severity(self):
        self.make_alert(severity='CRITICAL')
        self.make_alert(severity='LOW')

        response = self.client.get('/api/alerts/?severity=CRITICAL')

        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['severity'], 'CRITICAL')

    def test_the_severity_filter_is_case_insensitive(self):
        """`severity.upper()` in the viewset — pinned because a lowercase
        query string is the obvious thing for a client to send."""
        self.make_alert(severity='CRITICAL')

        response = self.client.get('/api/alerts/?severity=critical')

        self.assertEqual(response.data['count'], 1)

    def test_filtering_by_acknowledged(self):
        self.make_alert(acknowledged=True)
        self.make_alert(acknowledged=False)

        unacknowledged = self.client.get('/api/alerts/?acknowledged=false')
        acknowledged = self.client.get('/api/alerts/?acknowledged=true')

        self.assertEqual(unacknowledged.data['count'], 1)
        self.assertEqual(acknowledged.data['count'], 1)

    def test_the_acknowledged_filter_accepts_several_spellings(self):
        self.make_alert(acknowledged=True)

        for spelling in ('true', '1', 'yes', 'TRUE'):
            with self.subTest(spelling=spelling):
                response = self.client.get(f'/api/alerts/?acknowledged={spelling}')
                self.assertEqual(response.data['count'], 1)


class AlertAcknowledgementTests(AlertTestCase):
    """Acknowledgement is the one state change a client can make."""

    def test_acknowledging_records_who_and_when(self):
        alert = self.make_alert()

        response = self.client.patch(f'/api/alerts/{alert.pk}/acknowledge/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.acknowledged_by, self.owner)
        self.assertIsNotNone(alert.acknowledged_at)

    def test_acknowledging_twice_is_refused(self):
        """Otherwise the second call would overwrite the record of who first
        saw it, which is the only thing acknowledgement is for."""
        alert = self.make_alert(acknowledged=True)

        response = self.client.patch(f'/api/alerts/{alert.pk}/acknowledge/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_acknowledging_does_not_overwrite_the_first_acknowledger(self):
        alert = self.make_alert()
        self.client.patch(f'/api/alerts/{alert.pk}/acknowledge/')

        second = User.objects.create_user(username='second', password='x' * 12)
        Alert.objects.filter(pk=alert.pk).update(user=second)
        self.client.force_authenticate(user=second)
        self.client.patch(f'/api/alerts/{alert.pk}/acknowledge/')

        alert.refresh_from_db()
        self.assertEqual(alert.acknowledged_by, self.owner)

    def test_acknowledging_another_users_alert_is_a_404(self):
        stranger = User.objects.create_user(username='stranger', password='x' * 12)
        theirs = self.make_alert(owner=stranger)

        response = self.client.patch(f'/api/alerts/{theirs.pk}/acknowledge/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        theirs.refresh_from_db()
        self.assertFalse(theirs.acknowledged)


class AlertStatisticsTests(AlertTestCase):
    """GET /api/alerts/statistics/."""

    def test_counts_and_severity_breakdown(self):
        self.make_alert(severity='CRITICAL')
        self.make_alert(severity='CRITICAL')
        self.make_alert(severity='LOW', acknowledged=True)

        response = self.client.get('/api/alerts/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_alerts'], 3)
        self.assertEqual(response.data['unacknowledged_alerts'], 2)
        self.assertEqual(response.data['by_severity'], {'CRITICAL': 2, 'LOW': 1})

    def test_statistics_are_scoped_to_the_caller(self):
        stranger = User.objects.create_user(username='stranger', password='x' * 12)
        self.make_alert(owner=stranger)

        response = self.client.get('/api/alerts/statistics/')

        self.assertEqual(response.data['total_alerts'], 0)

    def test_recent_alerts_are_capped_and_newest_first(self):
        for i in range(12):
            self.make_alert(title=f'Alert {i}')

        response = self.client.get('/api/alerts/statistics/')

        recent = response.data['recent_alerts']
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0]['title'], 'Alert 11')


class AlertsAreReadOnlyTests(AlertTestCase):
    """Alerts are produced by threat detection, not posted by clients."""

    def test_creating_an_alert_over_the_api_is_refused(self):
        response = self.client.post('/api/alerts/', {
            'alert_type': 'INTRUSION', 'severity': 'CRITICAL',
            'title': 'Forged', 'description': 'Should not be possible.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(Alert.objects.count(), 0)

    def test_deleting_an_alert_is_refused(self):
        """An alert is a record of something that happened. Acknowledge it;
        do not erase it."""
        alert = self.make_alert()

        response = self.client.delete(f'/api/alerts/{alert.pk}/')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Alert.objects.filter(pk=alert.pk).exists())
