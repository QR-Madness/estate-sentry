"""Throttles for sensor endpoints."""

from rest_framework.throttling import SimpleRateThrottle


class SensorReadingRateThrottle(SimpleRateThrottle):
    """Bound how fast readings can be ingested, per sensor.

    `ScopedRateThrottle` is keyed on the user, which is the wrong unit here. An
    estate with twenty sensors would share one budget between all of them, so a
    single chatty camera could starve every contact sensor on the account, and
    the cap would have to be raised until it stopped meaning anything.

    The key is the sensor *and* its caller. Throttles are checked before the
    view body runs, so `get_object()` — the only thing that enforces ownership —
    has not happened yet; keying on the sensor alone would let any authenticated
    account drain a stranger's budget by posting to their sensor id and
    collecting 404s. In a security product that is worth closing: suppressing a
    sensor's readings is precisely the attack the system exists to notice.
    Including the caller gives an attacker a bucket of their own to exhaust
    while the owner's is untouched. A sensor has one owner, so on the legitimate
    path the pair is stable and the limit is exactly per-sensor, as intended.

    Carrying the scope on the class also sidesteps a DRF wrinkle: `throttle_scope`
    cannot be passed through `@action`, because `ViewSet.as_view()` rejects any
    initkwarg that is not already a class attribute. Scoping a throttle to one
    action the `ScopedRateThrottle` way therefore means putting the scope on the
    whole viewset, where it would also cover the CRUD routes.
    """

    scope = 'sensor-readings'

    def get_cache_key(self, request, view):
        # Anonymous requests never reach here — `IsAuthenticated` is checked
        # first — but returning None is the honest answer if they ever do: it
        # means "not throttled by this class" rather than sharing one bucket.
        if not request.user or not request.user.is_authenticated:
            return None

        sensor_pk = view.kwargs.get('pk')
        if sensor_pk is None:
            return None

        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{sensor_pk}.{request.user.pk}',
        }
