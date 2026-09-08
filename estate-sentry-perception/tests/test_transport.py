"""The wire contract between frame producers and the pipeline.

The format assertions here are deliberately literal. This contract is what lets
the Raspberry Pi edge agent replace the mock rig later without touching the
pipeline, so a drift in key layout or subject naming is a real break, not a
cosmetic one — and it would otherwise only surface as "no frames arrive".
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from perception.transport import (
    ALL_FRAMES_SUBJECT,
    FrameRef,
    InMemoryEventBus,
    InMemoryFrameStore,
    frame_key,
    frame_subject,
    subject_matches,
)

CAPTURED_AT = datetime(2026, 8, 30, 14, 5, 30, tzinfo=UTC)


# -- contract shape -----------------------------------------------------------


def test_frame_key_matches_the_documented_layout():
    # docs/architecture/switchboard.md: frames/{camera_id}/{date}/{iso}.jpg
    assert frame_key("front_door", CAPTURED_AT) == (
        "frames/front_door/2026-08-30/2026-08-30T14:05:30+00:00.jpg"
    )


def test_frame_subject_matches_the_documented_topic():
    # docs/Specification.md: frames.{camera_id}.raw
    assert frame_subject("front_door") == "frames.front_door.raw"


def test_wildcard_subject_matches_every_camera():
    assert subject_matches(ALL_FRAMES_SUBJECT, frame_subject("front_door"))
    assert subject_matches(ALL_FRAMES_SUBJECT, frame_subject("driveway"))


# -- FrameRef -----------------------------------------------------------------


def test_frame_ref_survives_a_json_round_trip():
    ref = FrameRef(
        camera_id="front_door",
        path=frame_key("front_door", CAPTURED_AT),
        captured_at=CAPTURED_AT,
        width=1920,
        height=1080,
        motion_detected=True,
    )
    assert FrameRef.from_json(ref.to_json()) == ref


def test_absent_motion_hint_is_distinct_from_a_negative_one():
    """`None` means the producer did not evaluate motion; `False` means it did
    and found none. Collapsing the two would make every hint-less producer look
    like a permanently quiet scene to the L1 gate."""
    unknown = FrameRef("c", "p", CAPTURED_AT, 640, 480)
    assert unknown.motion_detected is None

    checked = FrameRef("c", "p", CAPTURED_AT, 640, 480, motion_detected=False)
    assert checked.motion_detected is False
    assert FrameRef.from_json(unknown.to_json()).motion_detected is None


def test_naive_timestamps_are_read_back_as_utc():
    """A producer that publishes a naive timestamp should not yield a FrameRef
    that explodes on comparison with an aware one."""
    raw = b'{"camera_id":"c","path":"p","captured_at":"2026-08-30T14:05:30","width":1,"height":1,"motion_detected":null}'
    assert FrameRef.from_json(raw).captured_at == CAPTURED_AT


# -- subject matching (NATS semantics) ----------------------------------------


@pytest.mark.parametrize(
    ("pattern", "subject", "expected"),
    [
        ("frames.front_door.raw", "frames.front_door.raw", True),
        ("frames.*.raw", "frames.front_door.raw", True),
        ("frames.*.raw", "frames.front_door.hd", False),
        # `*` spans exactly one token, so it must not cross a dot.
        ("frames.*.raw", "frames.a.b.raw", False),
        ("frames.>", "frames.front_door.raw", True),
        ("frames.>", "frames", False),
        ("frames.front_door.raw", "frames.front_door", False),
        ("frames.front_door", "frames.front_door.raw", False),
    ],
)
def test_subject_matching_follows_nats_rules(pattern, subject, expected):
    assert subject_matches(pattern, subject) is expected


# -- in-memory implementations ------------------------------------------------


async def test_frame_store_round_trip():
    store = InMemoryFrameStore()
    key = await store.put("frames/c/2026-08-30/x.jpg", b"jpeg-bytes")
    assert await store.get(key) == b"jpeg-bytes"
    assert len(store) == 1


async def test_frame_store_raises_keyerror_for_a_missing_object():
    store = InMemoryFrameStore()
    with pytest.raises(KeyError):
        await store.get("frames/nope.jpg")


async def test_bus_delivers_to_every_matching_subscriber():
    bus = InMemoryEventBus()
    with (
        bus.subscribe("frames.front_door.raw") as exact,
        bus.subscribe(ALL_FRAMES_SUBJECT) as wildcard,
    ):
        await bus.publish("frames.front_door.raw", b"payload")

        assert await anext(exact) == b"payload"
        assert await anext(wildcard) == b"payload"


async def test_subscription_is_live_before_the_stream_is_first_advanced():
    """Regression: `subscribe()` used to be an async generator, which runs no
    code until first advanced. A message published between subscribing and
    iterating was therefore dropped on the floor — invisibly, and with the
    symptom surfacing much later as a missing frame."""
    bus = InMemoryEventBus()
    with bus.subscribe(ALL_FRAMES_SUBJECT) as stream:
        assert bus.subscriber_count == 1, "must be attached before first advance"

        # Published before anyone touches `stream`; must still be delivered.
        await bus.publish("frames.front_door.raw", b"early")

        assert await anext(stream) == b"early"


async def test_bus_does_not_deliver_to_non_matching_subscribers():
    bus = InMemoryEventBus()
    with bus.subscribe("frames.driveway.raw") as stream:
        await bus.publish("frames.front_door.raw", b"payload")

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(stream), timeout=0.05)


async def test_a_bounded_subscription_keeps_the_newest_messages():
    """The fix for detection boxes trailing the video.

    A consumer that does slow work per message must not accumulate a backlog:
    depth becomes staleness, and the pipeline ends up reporting on frames that
    have already left the screen. Bounded, newest-wins, is what keeps it current.
    """
    bus = InMemoryEventBus()
    with bus.subscribe(ALL_FRAMES_SUBJECT, max_queue=2) as stream:
        for i in range(10):
            await bus.publish("frames.c.raw", str(i).encode())

        first = await anext(stream)
        second = await anext(stream)

    assert (first, second) == (b"8", b"9"), "a slow consumer should see the latest"


async def test_bus_detaches_subscriber_on_context_exit():
    bus = InMemoryEventBus()
    with bus.subscribe(ALL_FRAMES_SUBJECT) as stream:
        await bus.publish("frames.c.raw", b"x")
        assert await anext(stream) == b"x"
        assert bus.subscriber_count == 1

    assert bus.subscriber_count == 0, "a disconnected consumer must not keep a queue attached"
