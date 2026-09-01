"""Back-pressure behaviour of the live fan-out.

These are the properties the whole design rests on, so they are asserted
directly rather than inferred from an end-to-end run: a slow consumer must not
stall the producer, memory must stay bounded, and the entry discarded under
pressure must be the oldest one.
"""

from __future__ import annotations

import time

import pytest

from perception.ring import FrameRing, TooManySubscribers


def test_publish_returns_monotonic_ids():
    ring: FrameRing[str] = FrameRing()
    ids = [ring.publish(f"f{i}").id for i in range(5)]
    assert ids == [1, 2, 3, 4, 5]


def test_history_is_bounded():
    ring: FrameRing[int] = FrameRing(history=10)
    for i in range(100):
        ring.publish(i)
    snapshot = ring.snapshot()
    assert len(snapshot) == 10
    # The retained window is the most recent one, not the earliest.
    assert [e.item for e in snapshot] == list(range(90, 100))


async def test_slow_subscriber_drops_oldest_and_stays_bounded():
    """The core guarantee: a subscriber that never reads cannot grow without
    bound, and what it loses is the stale end of the stream."""
    ring: FrameRing[int] = FrameRing(subscriber_queue_max=5)

    with ring.subscribe() as sub:
        for i in range(100):
            ring.publish(i)

        assert sub._queue.qsize() == 5, "queue must not exceed its bound"
        assert sub.dropped == 95, "every evicted entry should be counted"

        received = [(await sub.get()).item for _ in range(5)]

    # Survivors are the newest frames — a viewer catching up sees current
    # reality, not a backlog replayed in slow motion.
    assert received == [95, 96, 97, 98, 99]


async def test_publisher_never_blocks_on_a_stalled_consumer():
    """`publish` is synchronous by design, so it structurally cannot await a slow
    consumer. If that ever changed, one wedged browser tab would throttle capture
    for everyone — so this pins both the speed and the bound.

    Published from the event loop thread, which is the documented contract:
    producers doing blocking work in an executor are expected to hand results
    back via `loop.call_soon_threadsafe`."""
    ring: FrameRing[int] = FrameRing(subscriber_queue_max=1)

    with ring.subscribe() as stalled:  # a subscriber that never reads
        started = time.perf_counter()
        for i in range(10_000):
            ring.publish(i)
        elapsed = time.perf_counter() - started

    assert elapsed < 2.0, "publishing must not degrade with a stalled consumer"
    assert stalled._queue.qsize() == 1, "memory stays bounded regardless"
    assert ring.snapshot(limit=1)[0].item == 9_999


async def test_multiple_subscribers_each_get_their_own_queue():
    ring: FrameRing[str] = FrameRing()
    with ring.subscribe() as a, ring.subscribe() as b:
        ring.publish("x")
        assert (await a.get()).item == "x"
        assert (await b.get()).item == "x"


def test_subscribers_are_detached_on_context_exit():
    ring: FrameRing[str] = FrameRing()
    with ring.subscribe():
        assert ring.subscriber_count == 1
    assert ring.subscriber_count == 0, "a disconnected client must not linger"


def test_subscriber_cap_is_enforced():
    ring: FrameRing[str] = FrameRing(max_subscribers=2)
    with ring.subscribe(), ring.subscribe():
        with pytest.raises(TooManySubscribers):
            with ring.subscribe():
                pass


def test_snapshot_since_id_returns_only_the_gap():
    """What makes reconnection cheap: ask for what you missed, not everything."""
    ring: FrameRing[int] = FrameRing()
    for i in range(10):
        ring.publish(i)

    missed = ring.snapshot(since_id=7)
    assert [e.item for e in missed] == [7, 8, 9]
    assert [e.id for e in missed] == [8, 9, 10]


def test_snapshot_since_latest_id_is_empty():
    ring: FrameRing[int] = FrameRing()
    last = ring.publish(1)
    assert ring.snapshot(since_id=last.id) == []


def test_silence_is_measurable_before_and_after_first_publish():
    """The watchdog needs to distinguish 'never started' from 'stopped'."""
    ring: FrameRing[str] = FrameRing()
    assert ring.seconds_since_last_publish is None

    ring.publish("first")
    elapsed = ring.seconds_since_last_publish
    assert elapsed is not None and elapsed >= 0
