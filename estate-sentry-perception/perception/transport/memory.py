"""In-process implementations of the transport protocols.

These exist so the pipeline's behaviour — especially its behaviour under
back-pressure — can be tested without Docker, NATS or MinIO running. The
properties worth asserting (a full queue drops the oldest frame; a slow consumer
cannot stall the producer) are properties of our own code, not of the brokers,
so requiring infrastructure to check them would be pure friction.

Subject matching follows NATS semantics so a test that passes here is not
relying on a looser rule than production uses.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from .protocols import EventBus, FrameStore


def subject_matches(pattern: str, subject: str) -> bool:
    """NATS-style match: `*` spans one token, `>` spans all remaining tokens."""
    p_tokens = pattern.split(".")
    s_tokens = subject.split(".")
    for i, p in enumerate(p_tokens):
        if p == ">":
            return i < len(s_tokens)
        if i >= len(s_tokens):
            return False
        if p != "*" and p != s_tokens[i]:
            return False
    return len(p_tokens) == len(s_tokens)


class InMemoryFrameStore(FrameStore):
    """Dict-backed blob store."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self._objects[key] = data
        return key

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError:
            raise KeyError(f"no object at {key!r}") from None

    def __len__(self) -> int:
        return len(self._objects)

    @property
    def keys(self) -> list[str]:
        return list(self._objects)


class InMemoryEventBus(EventBus):
    """Fan-out bus with unbounded subscriber queues.

    Unbounded is correct *here* and nowhere else: a test wants to assert that
    every published message was observed, so silently dropping under load would
    make assertions flaky. The bounded, drop-oldest policy that production needs
    lives in `perception.ring.FrameRing`, which is where it is tested.
    """

    def __init__(self) -> None:
        self._subscribers: list[tuple[str, asyncio.Queue[bytes]]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        for pattern, queue in self._subscribers:
            if subject_matches(pattern, subject):
                queue.put_nowait(payload)

    @contextmanager
    def subscribe(self, subject: str) -> Iterator[AsyncIterator[bytes]]:
        """Attach on entry, detach on exit.

        Registration happens here, synchronously, rather than inside the async
        generator — otherwise nothing would be listening until the consumer first
        advanced the iterator, and messages published in between would vanish.
        """
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        entry = (subject, queue)
        self._subscribers.append(entry)
        try:
            yield self._drain(queue)
        finally:
            try:
                self._subscribers.remove(entry)
            except ValueError:  # pragma: no cover
                pass

    @staticmethod
    async def _drain(queue: asyncio.Queue[bytes]) -> AsyncIterator[bytes]:
        while True:
            yield await queue.get()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
