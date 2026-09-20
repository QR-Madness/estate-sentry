"""Health endpoint for the container healthcheck.

`docker-compose.yml` polls this every 30s to decide whether the api service is
healthy, so it reports on the dependencies whose absence would make the service
wrong rather than merely slow:

- the database, without which nothing works;
- the cache, because DRF counts rate limits in it. With the cache down the
  throttles do not degrade quietly, they raise — and an appliance that has
  stopped bounding authentication attempts should not be reporting itself
  healthy.
"""

from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

_PROBE_KEY = 'health-probe'


def _check_database():
    connection.ensure_connection()


def _check_cache():
    cache.set(_PROBE_KEY, '1', 5)
    if cache.get(_PROBE_KEY) != '1':
        # A cache that accepts a write and returns nothing is not a cache. This
        # is the failure a plain `cache.set` would miss.
        raise RuntimeError('cache did not return what was written to it')


@api_view(['GET'])
@permission_classes([AllowAny])  # a healthcheck cannot authenticate
@throttle_classes([])  # polled on a fixed interval; never throttle it
def health(request):
    """GET /api/health/ — 200 when every dependency answers, 503 otherwise."""
    checks = {}
    healthy = True

    for name, probe in (('database', _check_database), ('cache', _check_cache)):
        try:
            probe()
        except Exception as exc:
            # The message goes in the body, not the log stream: this is polled
            # every 30s and a broken dependency would otherwise flood it.
            checks[name] = f'error: {exc.__class__.__name__}'
            healthy = False
        else:
            checks[name] = 'ok'

    return Response(
        {'status': 'ok' if healthy else 'degraded', 'checks': checks},
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
