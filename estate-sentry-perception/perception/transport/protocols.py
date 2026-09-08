"""The seam between frame producers and the perception pipeline.

Everything upstream of the pipeline — the mock camera rig today, a Raspberry Pi
edge agent later — talks to it through exactly these two interfaces and the
`FrameRef` contract. Keeping them this narrow is the whole point: swapping the
mock for real hardware must be a configuration change, not a rewrite.

The wire contract is the one already specified in `docs/Specification.md` and
`docs/architecture/switchboard.md`:

    frame bytes  -> object store at frames/{camera_id}/{date}/{iso}.jpg
    notification -> subject frames.{camera_id}.raw

Note what does *not* travel on the bus: the frame itself. The notification
carries a reference, and consumers fetch the bytes from the store. A message bus
is the wrong place for megabytes of JPEG — it makes every subscriber pay for
payloads it may discard at the motion gate.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class FrameRef:
    """A pointer to one captured frame, as published on the bus.

    Deliberately small and JSON-serialisable — this crosses a process boundary
    and is persisted in JetStream, so it must stay cheap and version-tolerant.
    """

    camera_id: str
    path: str
    captured_at: datetime
    width: int
    height: int
    #: Producer-side motion hint. `None` means "producer did not evaluate
    #: motion", which is different from `False` ("producer checked, found none").
    #: The L1 gate needs that distinction to know whether it must do the work
    #: itself; collapsing them into a bool would make every hint-less producer
    #: look like a quiet scene and silently drop every frame.
    motion_detected: bool | None = None

    def to_json(self) -> bytes:
        payload = asdict(self)
        payload["captured_at"] = self.captured_at.isoformat()
        return json.dumps(payload).encode()

    @classmethod
    def from_json(cls, raw: bytes | str) -> FrameRef:
        payload = json.loads(raw)
        captured_at = datetime.fromisoformat(payload["captured_at"])
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        payload["captured_at"] = captured_at
        return cls(**payload)


def frame_key(camera_id: str, captured_at: datetime) -> str:
    """Object-store key for a frame. Matches the layout in switchboard.md."""
    return f"frames/{camera_id}/{captured_at.date().isoformat()}/{captured_at.isoformat()}.jpg"


def frame_subject(camera_id: str) -> str:
    """Bus subject a producer publishes frame notifications on."""
    return f"frames.{camera_id}.raw"


#: Wildcard for a consumer that wants every camera.
ALL_FRAMES_SUBJECT = "frames.*.raw"


@runtime_checkable
class FrameStore(Protocol):
    """Blob storage for frame bytes. MinIO in production, in-memory in tests."""

    async def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        """Store `data` at `key`; return the key."""
        ...

    async def get(self, key: str) -> bytes:
        """Fetch the bytes at `key`. Raises `KeyError` if absent."""
        ...


@runtime_checkable
class EventBus(Protocol):
    """Publish/subscribe. NATS in production, in-memory in tests."""

    async def publish(self, subject: str, payload: bytes) -> None: ...

    def subscribe(
        self, subject: str, *, max_queue: int | None = None
    ) -> AbstractContextManager[AsyncIterator[bytes]]:
        """Register interest in `subject` for the duration of the context.

        `max_queue` bounds how many undelivered messages are held for this
        subscriber. A relaying consumer wants slack; one doing slow work per
        message wants almost none, because depth turns directly into staleness.

        A context manager rather than a bare async generator, and the distinction
        is load-bearing. An async generator runs no code until it is first
        advanced, so `stream = bus.subscribe(subj)` would leave the subscription
        *unregistered* until the consumer got round to iterating — and every
        message published in that window would be lost, silently, with the
        symptom appearing much later as "the pipeline missed a frame".

        Entering the context registers immediately; leaving it detaches, so a
        disconnected consumer cannot leave a queue behind for the producer to
        keep filling.

            with bus.subscribe(ALL_FRAMES_SUBJECT) as stream:
                async for payload in stream:
                    ...
        """
        ...
