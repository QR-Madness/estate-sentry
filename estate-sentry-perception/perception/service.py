"""The perception service: subscribe, fetch, gate, detect, report.

Wires the pieces together and owns the runtime concerns that only appear once
something is actually running — back-pressure, dead air, and failures in one
camera not taking down the others.

Layer coverage is L1 (motion gate), L2 (object detection) and L3 (zone
intersection). L4 onward — identity, action, correlation, threat scoring — are
not built.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import cv2
import numpy as np

from .api_client import ApiClient
from .constants import (
    WATCHDOG_REPEAT_SECONDS,
    WATCHDOG_SILENCE_SECONDS,
    ZONE_ANCHOR,
)
from .pipeline.detect import Detection, Detector, StubDetector
from .pipeline.motion import MotionGate
from .pipeline.zones import ZoneIndex
from .ring import FrameRing
from .transport.protocols import (
    ALL_FRAMES_SUBJECT,
    EventBus,
    FrameRef,
    FrameStore,
)

logger = logging.getLogger(__name__)

DETECTIONS_SUBJECT = "detections.{camera_id}"
STATUS_SUBJECT = "perception.status"


@dataclass(slots=True)
class DetectionEvent:
    """What the pipeline emits for one processed frame."""

    camera_id: str
    frame_path: str
    captured_at: datetime
    motion: bool
    motion_reason: str
    detections: list[Detection] = field(default_factory=list)
    #: Zone names each detection landed in, positionally aligned with
    #: `detections`. A list per detection, since perimeters may overlap.
    zones: list[list[str]] = field(default_factory=list)

    def to_json(self) -> bytes:
        payload = asdict(self)
        payload["captured_at"] = self.captured_at.isoformat()
        return json.dumps(payload).encode()


@dataclass(slots=True)
class Stats:
    """Counters, so 'is it working' has an answer that is not a log grep."""

    frames_seen: int = 0
    gated_out: int = 0
    detections: int = 0
    zone_events: int = 0
    #: Detections that matched no zone. Tracked separately because a high count
    #: usually means a perimeter is wrong or missing, not that nothing happened —
    #: and that is invisible if it is folded into the totals.
    outside_zones: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def decode_jpeg_gray(data: bytes) -> np.ndarray:
    """Decode to grayscale — the only form the motion gate needs.

    Decoding straight to grayscale rather than colour-then-convert is roughly a
    third less work per frame, and at the gate stage colour is never consulted.
    """
    array = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        raise ValueError("could not decode frame as JPEG")
    return frame


def decode_jpeg_colour(data: bytes) -> np.ndarray:
    """Decode to RGB, which is what the detector expects."""
    array = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("could not decode frame as JPEG")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


class PerceptionService:
    def __init__(
        self,
        store: FrameStore,
        bus: EventBus,
        *,
        detector: Detector | None = None,
        gate: MotionGate | None = None,
        ring: FrameRing[DetectionEvent] | None = None,
        api: ApiClient | None = None,
        zone_index: ZoneIndex | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.api = api
        # Empty until loaded. An empty index is a working state, not an error:
        # the pipeline still detects, it just cannot say where.
        self.zones = zone_index or ZoneIndex()
        # A stub by default: the service must be constructible, importable and
        # runnable without the multi-gigabyte `detect` extra installed.
        self.detector = detector or StubDetector()
        self.gate = gate or MotionGate()
        self.ring: FrameRing[DetectionEvent] = ring or FrameRing()
        self.stats = Stats()

    # -- frame handling -------------------------------------------------------

    async def handle_frame(self, ref: FrameRef) -> DetectionEvent | None:
        """Process one frame reference. Returns None if the gate rejected it."""
        self.stats.frames_seen += 1
        data = await self.store.get(ref.path)

        # Decode and inference are CPU-bound; on the event loop they would block
        # every other camera and the watchdog behind them.
        gray = await asyncio.to_thread(decode_jpeg_gray, data)
        motion = self.gate.evaluate(
            ref.camera_id, gray, producer_hint=ref.motion_detected
        )

        if not motion.motion:
            self.stats.gated_out += 1
            logger.debug(
                "%s: gated out (%s, changed=%.4f)",
                ref.camera_id,
                motion.reason,
                motion.changed_fraction,
            )
            return None

        colour = await asyncio.to_thread(decode_jpeg_colour, data)
        detections = await asyncio.to_thread(self.detector.detect, colour)
        self.stats.detections += len(detections)

        # L3: which zone, if any, did each detection land in?
        zone_names, zone_events = self._locate(ref, detections)

        event = DetectionEvent(
            camera_id=ref.camera_id,
            frame_path=ref.path,
            captured_at=ref.captured_at,
            motion=True,
            motion_reason=motion.reason,
            detections=detections,
            zones=zone_names,
        )

        # Log everything, before anything downstream decides the detection was
        # uninteresting. A record that only keeps what already looked suspicious
        # cannot answer the question people actually ask after an incident.
        if zone_events and self.api is not None:
            written = await self.api.post_zone_events(zone_events)
            self.stats.zone_events += written

        self.ring.publish(event)
        await self.bus.publish(
            DETECTIONS_SUBJECT.format(camera_id=ref.camera_id), event.to_json()
        )

        if detections:
            logger.info(
                "%s: %s",
                ref.camera_id,
                ", ".join(
                    f"{d.label}({d.category}) {d.confidence:.2f}" for d in detections
                ),
            )
        return event

    def _locate(
        self, ref: FrameRef, detections: list[Detection]
    ) -> tuple[list[list[str]], list[dict]]:
        """Match detections to zones, and build the log entries for them.

        Returns names per detection (for the live event, positionally aligned
        with `detections`) and payloads for the zone event log.
        """
        names: list[list[str]] = []
        payloads: list[dict] = []
        frame_size = (ref.width, ref.height)

        for detection in detections:
            matches = self.zones.matches(
                ref.camera_id, detection.anchor(ZONE_ANCHOR), frame_size
            )
            names.append([m.zone_name for m in matches])

            if not matches:
                self.stats.outside_zones += 1
                continue

            # Boxes are stored normalised, matching ZonePerimeter.polygon, so a
            # resolution change does not invalidate historical geometry.
            x1, y1, x2, y2 = detection.box
            box = [
                round(x1 / ref.width, 5),
                round(y1 / ref.height, 5),
                round(x2 / ref.width, 5),
                round(y2 / ref.height, 5),
            ]
            for match in matches:
                payloads.append(
                    {
                        "zone": match.zone_id,
                        "camera": match.camera_pk,
                        "timestamp": ref.captured_at.isoformat(),
                        "object_class": detection.category,
                        "confidence": detection.confidence,
                        "bounding_box": box,
                        "frame_path": ref.path,
                        "metadata": {"label": detection.label},
                    }
                )

        return names, payloads

    # -- run loop -------------------------------------------------------------

    async def run(self, *, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()

        if self.api is not None and len(self.zones) == 0:
            self.zones = await self.api.fetch_zone_index()
        if len(self.zones) == 0:
            # Said plainly at startup, because the symptom otherwise is an empty
            # zone event log with a pipeline that looks perfectly healthy.
            logger.warning(
                "no zone perimeters loaded: detections will be reported but not "
                "attributed to any zone, and nothing will be written to the event log"
            )

        watchdog = asyncio.create_task(self._watchdog(stop))
        try:
            with self.bus.subscribe(ALL_FRAMES_SUBJECT) as stream:
                logger.info("subscribed to %s", ALL_FRAMES_SUBJECT)
                consumer = asyncio.create_task(self._consume(stream))
                stopper = asyncio.create_task(stop.wait())
                await asyncio.wait(
                    {consumer, stopper}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in (consumer, stopper):
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await consumer
        finally:
            watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watchdog
            logger.info("stopped: %s", self.stats.as_dict())

    async def _consume(self, stream) -> None:
        async for payload in stream:
            try:
                ref = FrameRef.from_json(payload)
            except (ValueError, KeyError, TypeError):
                # A malformed message must not kill the subscription — that would
                # turn one bad publisher into a total outage.
                self.stats.errors += 1
                logger.warning("discarding unparseable frame notification", exc_info=True)
                continue

            try:
                await self.handle_frame(ref)
            except Exception:
                self.stats.errors += 1
                logger.exception("failed to process frame %s", ref.path)

    async def _watchdog(self, stop: asyncio.Event) -> None:
        """Announce dead air.

        Without this, a stalled capture loop is indistinguishable from a quiet
        driveway: both produce no output at all. Reporting silence explicitly is
        what makes the difference visible.
        """
        announced_at: float | None = None
        while not stop.is_set():
            await asyncio.sleep(1.0)
            silence = self.ring.seconds_since_last_publish
            if silence is None or silence < WATCHDOG_SILENCE_SECONDS:
                announced_at = None
                continue
            if announced_at is not None and silence - announced_at < WATCHDOG_REPEAT_SECONDS:
                continue
            announced_at = silence
            logger.warning("no frames for %.0fs", silence)
            with contextlib.suppress(Exception):
                await self.bus.publish(
                    STATUS_SUBJECT,
                    json.dumps(
                        {
                            "event": "silence",
                            "seconds": round(silence, 1),
                            "at": datetime.now(UTC).isoformat(),
                            "stats": self.stats.as_dict(),
                        }
                    ).encode(),
                )
