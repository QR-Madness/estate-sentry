"""Bounded fan-out of live items to subscribers, dropping oldest under load.

Adapted from the same pattern in AgentX (`api/agentx_ai/logging_kit/ring_buffer.py`),
which solves the identical problem for log records: a slow SSE client must be
unable to either stall the producer or grow memory without bound.

Frames make the argument sharper than logs did. When a viewer cannot keep up, the
right thing to discard is the *oldest* pending frame, because a stale frame has
no value — nobody wants to watch a growing delay play out in slow motion. So the
queue is bounded and full queues evict from the front. Blocking the producer, the
usual alternative, would couple capture rate to the slowest browser tab on the
network, which is exactly the failure this class exists to prevent.

Producers call `publish()`, which never awaits and never raises on a slow
consumer. Consumers hold a `Subscription` and await items.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import count
from typing import Generic, TypeVar

from .constants import (
    RING_HISTORY,
    RING_MAX_SUBSCRIBERS,
    RING_SUBSCRIBER_QUEUE_MAX,
)

T = TypeVar("T")


class TooManySubscribers(RuntimeError):
    """Raised when the subscriber cap is reached.

    A cap, rather than unbounded growth, because each subscriber costs a queue of
    up to RING_SUBSCRIBER_QUEUE_MAX items; without a ceiling, opening browser tabs
    is an unauthenticated way to exhaust memory.
    """


@dataclass(slots=True)
class Entry(Generic[T]):
    """One published item, tagged with a monotonic id for cursor-based catch-up."""

    id: int
    item: T


class Subscription(Generic[T]):
    """A live feed of entries. Obtain one via `FrameRing.subscribe()`."""

    __slots__ = ("_queue", "dropped")

    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[Entry[T]] = asyncio.Queue(maxsize=maxsize)
        #: Count of entries evicted before this subscriber could read them.
        #: Surfaced rather than hidden: silent loss looks identical to an idle
        #: camera from the outside, and that ambiguity costs real debugging time.
        self.dropped = 0

    async def get(self) -> Entry[T]:
        return await self._queue.get()

    def offer(self, entry: Entry[T]) -> None:
        """Non-blocking enqueue; evicts the oldest entry when full."""
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:  # pragma: no cover — drained concurrently
                pass
            try:
                self._queue.put_nowait(entry)
            except asyncio.QueueFull:  # pragma: no cover — refilled concurrently
                self.dropped += 1

    def __aiter__(self) -> Subscription[T]:
        return self

    async def __anext__(self) -> Entry[T]:
        return await self.get()


class FrameRing(Generic[T]):
    """Recent-history buffer plus bounded live fan-out.

    Not thread-safe: `publish()` must be called from the event loop thread. Frame
    decoding is blocking work that belongs in an executor, so a producer doing
    that should hand results back with `loop.call_soon_threadsafe(ring.publish, x)`
    rather than calling this directly from the worker thread.
    """

    def __init__(
        self,
        *,
        history: int = RING_HISTORY,
        subscriber_queue_max: int = RING_SUBSCRIBER_QUEUE_MAX,
        max_subscribers: int = RING_MAX_SUBSCRIBERS,
    ) -> None:
        self._history: deque[Entry[T]] = deque(maxlen=history)
        self._subscribers: list[Subscription[T]] = []
        self._ids = count(1)
        self._subscriber_queue_max = subscriber_queue_max
        self._max_subscribers = max_subscribers
        self._last_publish_monotonic: float | None = None

    # -- producer side --------------------------------------------------------

    def publish(self, item: T) -> Entry[T]:
        entry = Entry(id=next(self._ids), item=item)
        self._history.append(entry)
        self._last_publish_monotonic = time.monotonic()
        for sub in self._subscribers:
            sub.offer(entry)
        return entry

    @property
    def seconds_since_last_publish(self) -> float | None:
        """Age of the most recent publish, or None if nothing has been published.

        The dead-air watchdog reads this. Monotonic, so a clock adjustment cannot
        make a stalled pipeline look healthy.
        """
        if self._last_publish_monotonic is None:
            return None
        return time.monotonic() - self._last_publish_monotonic

    # -- consumer side --------------------------------------------------------

    @contextmanager
    def subscribe(self) -> Iterator[Subscription[T]]:
        """Attach a live subscriber for the duration of the context.

        A context manager because the failure mode it prevents — a disconnected
        client leaving its queue attached, so the producer keeps filling a buffer
        nobody reads — is otherwise easy to introduce and hard to notice.
        """
        if len(self._subscribers) >= self._max_subscribers:
            raise TooManySubscribers(
                f"at most {self._max_subscribers} concurrent subscribers"
            )
        sub: Subscription[T] = Subscription(self._subscriber_queue_max)
        self._subscribers.append(sub)
        try:
            yield sub
        finally:
            try:
                self._subscribers.remove(sub)
            except ValueError:  # pragma: no cover — removed twice
                pass

    def snapshot(self, *, since_id: int | None = None, limit: int | None = None) -> list[Entry[T]]:
        """Buffered history, optionally only entries newer than `since_id`.

        This is what makes a reconnect cheap: a client that dropped at id N asks
        for `since_id=N` and receives only what it missed, instead of replaying
        the whole buffer.
        """
        items = list(self._history)
        if since_id is not None:
            items = [e for e in items if e.id > since_id]
        if limit is not None:
            items = items[-limit:]
        return items

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
