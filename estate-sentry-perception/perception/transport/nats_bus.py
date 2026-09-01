"""NATS-backed message bus.

`nats-py` is async-native, so unlike the MinIO store nothing needs offloading.

Subscription registration is done eagerly in `subscribe()`, before the caller
touches the returned iterator, for the same reason the in-memory bus does it:
attaching lazily would silently drop everything published between subscribing and
first iterating.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from ..constants import RING_SUBSCRIBER_QUEUE_MAX
from .protocols import EventBus

logger = logging.getLogger(__name__)


class NatsEventBus(EventBus):
    """Publish/subscribe over NATS.

    Construct with `await NatsEventBus.connect(url)`; a bare constructor cannot
    await, and connecting lazily on first publish would hide connection failures
    until the first frame instead of surfacing them at startup.
    """

    def __init__(self, client: NATSClient) -> None:
        self._client = client

    @classmethod
    async def connect(cls, url: str | None = None, **options) -> NatsEventBus:
        url = url or os.environ.get("NATS_URL", "nats://localhost:4222")
        client = await nats.connect(url, **options)
        logger.info("connected to NATS at %s", url)
        return cls(client)

    async def publish(self, subject: str, payload: bytes) -> None:
        await self._client.publish(subject, payload)

    @contextmanager
    def subscribe(self, subject: str) -> Iterator[AsyncIterator[bytes]]:
        """Attach a subscription for the duration of the context.

        Bounded, and dropping the oldest message when full, matching the policy in
        `perception.ring`. NATS would otherwise buffer for a slow consumer until
        it hit its own limits and dropped the subscriber outright — losing the
        whole stream rather than the stale end of it.
        """
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=RING_SUBSCRIBER_QUEUE_MAX)

        async def _on_message(msg: Msg) -> None:
            try:
                queue.put_nowait(msg.data)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:  # pragma: no cover
                    pass
                else:
                    logger.debug("dropped oldest message on %s (slow consumer)", subject)
                try:
                    queue.put_nowait(msg.data)
                except asyncio.QueueFull:  # pragma: no cover
                    pass

        # Registration is scheduled here rather than awaited, because this is a
        # sync context manager. The task is awaited on exit so failures surface.
        sub_task = asyncio.ensure_future(
            self._client.subscribe(subject, cb=_on_message)
        )

        async def _drain() -> AsyncIterator[bytes]:
            await sub_task  # ensure the subscription is live before yielding
            while True:
                yield await queue.get()

        try:
            yield _drain()
        finally:
            asyncio.ensure_future(self._unsubscribe(sub_task))

    @staticmethod
    async def _unsubscribe(sub_task: asyncio.Future) -> None:
        try:
            subscription = await sub_task
            await subscription.unsubscribe()
        except Exception:  # pragma: no cover — teardown must not mask the real error
            logger.debug("failed to unsubscribe cleanly", exc_info=True)

    async def close(self) -> None:
        await self._client.drain()
