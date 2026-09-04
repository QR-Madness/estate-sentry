"""Live data for the dashboard: one bus subscription per camera, fanned out.

The dashboard is a *consumer* of the Switchboard, exactly like the perception
service — it does not talk to the pipeline at all. That matters for a reason
beyond tidiness: the camera view keeps working when perception is down. You can
still see the driveway while inference is being restarted.

The shape of the problem is fan-out. Naively, each viewer would open its own
subscription and fetch every frame from object storage itself, so five people
watching one camera would mean five identical MinIO reads per frame. Instead
each camera gets exactly one pump — one subscription, one fetch — publishing
into a `FrameRing`, and viewers attach to that. The ring already provides the
bounded, drop-oldest behaviour that a slow browser needs, so a viewer on a bad
connection degrades to a lower frame rate instead of consuming memory or
slowing anyone else down.

Pumps are reference-counted: started when the first viewer arrives, stopped when
the last one leaves, so an unwatched camera costs nothing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator

from perception.ring import FrameRing, Subscription
from perception.transport.minio_store import MinioFrameStore
from perception.transport.nats_bus import NatsEventBus
from perception.transport.protocols import FrameRef, frame_subject

logger = logging.getLogger(__name__)

#: Detection events from the pipeline, and its own health reports.
DETECTIONS_SUBJECT = "detections.*"
STATUS_SUBJECT = "perception.status"


class CameraFeed:
    """One pump per camera, fanned out to every viewer of it."""

    def __init__(self, camera_id: str, bridge: LiveBridge) -> None:
        self.camera_id = camera_id
        self._bridge = bridge
        self.ring: FrameRing[bytes] = FrameRing()
        self._viewers = 0
        self._task: asyncio.Task | None = None

    @contextlib.asynccontextmanager
    async def viewer(self) -> AsyncIterator[Subscription[bytes]]:
        """Attach a viewer, starting the pump if it is the first."""
        self._viewers += 1
        if self._task is None:
            self._task = asyncio.create_task(self._pump())
            logger.info("%s: pump started", self.camera_id)
        try:
            with self.ring.subscribe() as sub:
                yield sub
        finally:
            self._viewers -= 1
            if self._viewers <= 0 and self._task is not None:
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task
                self._task = None
                logger.info("%s: pump stopped (no viewers)", self.camera_id)

    async def _pump(self) -> None:
        bus = await self._bridge.bus()
        store = await self._bridge.store()
        with bus.subscribe(frame_subject(self.camera_id)) as stream:
            async for payload in stream:
                try:
                    ref = FrameRef.from_json(payload)
                    data = await store.get(ref.path)
                except Exception:
                    # One unreadable frame must not end the stream — that would
                    # turn a transient storage blip into a dead camera tile.
                    logger.warning("%s: skipping a frame", self.camera_id, exc_info=True)
                    continue
                self.ring.publish(data)


class LiveBridge:
    """Process-wide clients and per-camera feeds for the web process.

    Connections are made lazily, on the running event loop, rather than at import
    time: Django imports this module during `manage.py check` and management
    commands, where there is no loop and no reason to require NATS to be up.
    """

    def __init__(self) -> None:
        self._bus: NatsEventBus | None = None
        self._store: MinioFrameStore | None = None
        self._feeds: dict[str, CameraFeed] = {}
        self._events: FrameRing[bytes] = FrameRing()
        self._events_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def bus(self) -> NatsEventBus:
        async with self._lock:
            if self._bus is None:
                self._bus = await NatsEventBus.connect(
                    os.environ.get("NATS_URL", "nats://localhost:4222")
                )
            return self._bus

    async def store(self) -> MinioFrameStore:
        async with self._lock:
            if self._store is None:
                self._store = MinioFrameStore.from_env()
            return self._store

    def feed(self, camera_id: str) -> CameraFeed:
        if camera_id not in self._feeds:
            self._feeds[camera_id] = CameraFeed(camera_id, self)
        return self._feeds[camera_id]

    # -- pipeline events ------------------------------------------------------

    @contextlib.asynccontextmanager
    async def events(self) -> AsyncIterator[Subscription[bytes]]:
        """Attach to the detection/status stream, starting its pump if needed.

        Unlike camera pumps this one is never stopped. The event ring is the
        dashboard's short history, and tearing it down when the last tab closes
        would mean the next visitor sees an empty feed rather than what just
        happened — which is the opposite of useful for an alert list.
        """
        if self._events_task is None:
            self._events_task = asyncio.create_task(self._pump_events())
            logger.info("event pump started")
        with self._events.subscribe() as sub:
            yield sub

    async def _pump_events(self) -> None:
        bus = await self.bus()
        with bus.subscribe(DETECTIONS_SUBJECT) as detections:
            async for payload in detections:
                self._events.publish(payload)

    def event_history(self, *, since_id: int | None = None, limit: int = 50):
        """Backlog for a reconnecting client, so it catches up on the gap only."""
        return self._events.snapshot(since_id=since_id, limit=limit)

    @property
    def cameras(self) -> list[str]:
        return sorted(self._feeds)


#: Module-level singleton. One per web process, which is what "one pump per
#: camera" means in practice — running multiple ASGI workers gives each its own.
bridge = LiveBridge()
