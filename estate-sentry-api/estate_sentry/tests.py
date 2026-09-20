"""The health endpoint.

Weighted towards the cases that made it worth adding: that it answers without
credentials, and that it actually fails when a dependency is down. A healthcheck
that always returns 200 is worse than none, because it reports confidence it has
not earned.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_it_answers_without_credentials(self):
        """The container healthcheck has no token; DRF defaults to
        IsAuthenticated, so this would otherwise be a permanent 401."""
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_it_reports_each_dependency(self):
        response = self.client.get('/api/health/')

        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(
            response.data['checks'], {'database': 'ok', 'cache': 'ok'}
        )

    def test_a_failed_dependency_is_a_503(self):
        with patch(
            'estate_sentry.health._check_cache', side_effect=RuntimeError('down')
        ):
            response = self.client.get('/api/health/')

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE,
            'a broken dependency must not report as healthy',
        )
        self.assertEqual(response.data['status'], 'degraded')
        self.assertEqual(response.data['checks']['database'], 'ok')
        self.assertIn('error', response.data['checks']['cache'])

    def test_every_dependency_is_probed_even_after_one_fails(self):
        """A failure in the first probe must not mask the state of the rest."""
        with patch(
            'estate_sentry.health._check_database',
            side_effect=RuntimeError('down'),
        ):
            response = self.client.get('/api/health/')

        self.assertIn('error', response.data['checks']['database'])
        self.assertEqual(response.data['checks']['cache'], 'ok')

    def test_a_cache_that_swallows_writes_is_unhealthy(self):
        """The failure a plain `cache.set` would miss: accepted, not stored."""
        with patch('estate_sentry.health.cache.get', return_value=None):
            response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
