"""Middleware that writes security events to the audit log.

Three things decide whether this works at all.

**It is allowlisted, not blanket.** A row per request would put a database write
on the ingest hot path — 60 readings a minute per sensor — duplicating what
`SensorReading` already records, and would fill the log with healthcheck polls.
Only the events below are audited: authentication, device lifecycle, and changes
to the configuration that decides what the system watches and alerts on. Reads
are not audited; changes are.

**It is async-capable.** The project runs under ASGI and `hq/views.py` serves
long-lived MJPEG and SSE responses. An async middleware calling the ORM directly
raises `SynchronousOnlyOperation`, so the write goes through `sync_to_async` —
and the allowlist is consulted *before* that hop, so a streaming request never
pays for a thread it does not need.

**It cannot fail the request.** An audit log that takes the service down with it
is worse than no audit log. Every failure is caught and logged.
"""

import logging

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async

from .context import get_audit_context
from .models import AuditLog

logger = logging.getLogger(__name__)

#: (view_name, method) -> action. `view_name` is the namespaced name from
#: `request.resolver_match`; see `django.urls.resolve`.
AUDITED = {
    ('authentication:login', 'POST'): 'LOGIN',
    ('authentication:logout', 'POST'): 'LOGOUT',
    ('authentication:register', 'POST'): 'REGISTER',
    ('authentication:user-detail', 'PUT'): 'USER_UPDATE',
    ('authentication:user-detail', 'PATCH'): 'USER_UPDATE',
    ('authentication:devices', 'POST'): 'DEVICE_ENROL',
    ('authentication:device-revoke', 'POST'): 'DEVICE_REVOKE',

    ('sensors:sensor-list', 'POST'): 'SENSOR_CREATE',
    ('sensors:sensor-detail', 'PUT'): 'SENSOR_UPDATE',
    ('sensors:sensor-detail', 'PATCH'): 'SENSOR_UPDATE',
    ('sensors:sensor-detail', 'DELETE'): 'SENSOR_DELETE',

    ('alerts:alert-acknowledge', 'PATCH'): 'ALERT_ACKNOWLEDGE',

    # Zone geometry decides where alerts fire, so changing it is a security
    # change. These routes are not namespaced — `zones/urls.py` sets no
    # `app_name`.
    ('zone-list', 'POST'): 'ZONE_CREATE',
    ('zone-detail', 'PUT'): 'ZONE_UPDATE',
    ('zone-detail', 'PATCH'): 'ZONE_UPDATE',
    ('zone-detail', 'DELETE'): 'ZONE_DELETE',
}

#: Deliberately absent, and why:
#:   sensors:sensor-readings     ingest; SensorReading is already the record
#:   health                      polled every 30s by the container healthcheck
#:   hq:camera-mjpeg             long-lived stream
#:   hq:events-stream            long-lived stream
#:   every GET                   reads are not changes


def _outcome_for(status_code):
    if 200 <= status_code < 300:
        return 'SUCCESS'
    if status_code in (401, 403):
        return 'DENIED'
    return 'FAILURE'


def _client_ip(request):
    """The client address, preferring the proxy header when one is present.

    `REMOTE_ADDR` behind a reverse proxy is the proxy. The left-most entry of
    `X-Forwarded-For` is the client as the nearest proxy saw it — spoofable by
    the client itself, so this is a hint for an investigator, not an identity.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


class AuditMiddleware:
    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

        response = self.get_response(request)
        if self._action_for(request) is not None:
            self._safe_record(request, response)
        return response

    async def __acall__(self, request):
        response = await self.get_response(request)
        # Checked before the thread hop: a streaming response must not pay for
        # one, and nothing here touches the ORM until we know we are writing.
        if self._action_for(request) is not None:
            await sync_to_async(self._safe_record, thread_sensitive=True)(
                request, response
            )
        return response

    @staticmethod
    def _action_for(request):
        match = getattr(request, 'resolver_match', None)
        if match is None:
            # Unresolved (a 404) — there is no view to attribute anything to.
            return None
        return AUDITED.get((match.view_name, request.method))

    def _safe_record(self, request, response):
        try:
            self._record(request, response)
        except Exception:
            # Never fail a request because the audit write failed. The log is
            # the fallback record of the thing we could not record.
            logger.exception(
                'Failed to write audit entry for %s %s', request.method, request.path
            )

    def _record(self, request, response):
        action = self._action_for(request)
        context = dict(get_audit_context(request))

        actor = context.pop('actor', None)
        if actor is None:
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated:
                actor = user

        actor_username = context.pop('actor_username', '')
        if not actor_username and actor is not None:
            actor_username = actor.get_username()

        AuditLog.objects.create(
            actor=actor,
            actor_username=actor_username or '',
            action=action,
            outcome=context.pop('outcome', None) or _outcome_for(response.status_code),
            target_type=context.pop('target_type', '') or '',
            target_id=str(context.pop('target_id', '') or ''),
            method=request.method,
            path=request.path[:512],
            status_code=response.status_code,
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
            metadata=context.pop('metadata', {}) or {},
        )
