"""L1 motion gate behaviour.

The gate decides what the expensive layers never see, so its failure modes are
asymmetric: a false positive costs one inference, a false negative loses an
event permanently. The tests lean on that asymmetry — several of them exist to
pin cases where the gate must let a frame *through* rather than be clever.
"""

from __future__ import annotations

import numpy as np

from perception.pipeline.motion import MotionGate


def blank(value: int = 0, size: tuple[int, int] = (120, 160)) -> np.ndarray:
    return np.full(size, value, dtype=np.uint8)


def with_blob(fraction: float, size: tuple[int, int] = (120, 160)) -> np.ndarray:
    """A dark frame with a bright rectangle covering roughly `fraction` of it."""
    frame = blank(0, size)
    pixels = int(frame.size * fraction)
    rows = max(1, pixels // size[1])
    frame[:rows, :] = 255
    return frame


# -- frames that must always pass ---------------------------------------------


def test_first_frame_from_a_camera_always_passes():
    """Nothing to compare against, and the moment right after a restart is
    exactly when something may be happening."""
    gate = MotionGate()
    result = gate.evaluate("front_door", blank())
    assert result.motion is True
    assert result.reason == "first-frame"


def test_resolution_change_passes_rather_than_comparing_junk():
    gate = MotionGate()
    gate.evaluate("front_door", blank(size=(120, 160)))
    result = gate.evaluate("front_door", blank(size=(240, 320)))
    assert result.motion is True
    assert result.reason == "resolution-changed"


# -- differencing -------------------------------------------------------------


def test_identical_frames_are_not_motion():
    gate = MotionGate()
    gate.evaluate("front_door", blank())
    result = gate.evaluate("front_door", blank())
    assert result.motion is False
    assert result.reason == "differenced"
    assert result.changed_fraction == 0.0


def test_a_large_change_is_motion():
    gate = MotionGate()
    gate.evaluate("front_door", blank())
    result = gate.evaluate("front_door", with_blob(0.10))
    assert result.motion is True
    assert result.changed_fraction > 0.05


def test_a_change_below_the_area_threshold_is_ignored():
    """Sensor noise and compression artefacts must not wake the pipeline."""
    gate = MotionGate(area_fraction=0.05)
    gate.evaluate("front_door", blank())
    result = gate.evaluate("front_door", with_blob(0.01))
    assert result.motion is False


def test_a_change_below_the_pixel_delta_is_ignored():
    """A uniform brightness drift — cloud passing, auto-exposure — moves every
    pixel a little. Judged per pixel, that is not motion."""
    gate = MotionGate(pixel_delta=50)
    gate.evaluate("front_door", blank(100))
    result = gate.evaluate("front_door", blank(120))  # every pixel +20, under 50
    assert result.motion is False
    assert result.changed_fraction == 0.0


def test_cameras_are_tracked_independently():
    """One camera's frame must never be differenced against another's."""
    gate = MotionGate()
    gate.evaluate("front_door", blank(0))
    gate.evaluate("driveway", blank(255))

    # Unchanged for its own camera, despite differing wildly from the other's.
    assert gate.evaluate("front_door", blank(0)).motion is False
    assert set(gate.tracked_cameras) == {"front_door", "driveway"}


# -- producer hints -----------------------------------------------------------


def test_a_positive_producer_hint_is_trusted():
    gate = MotionGate()
    result = gate.evaluate("front_door", blank(), producer_hint=True)
    assert result.motion is True
    assert result.reason == "producer-hint"


def test_a_negative_producer_hint_short_circuits_the_diff():
    gate = MotionGate()
    gate.evaluate("front_door", blank(0))
    result = gate.evaluate("front_door", with_blob(0.5), producer_hint=False)
    assert result.motion is False, "an explicit hint wins over differencing"
    assert result.reason == "producer-hint"


def test_an_absent_hint_falls_through_to_differencing():
    """`None` is not `False`: a producer that never evaluates motion must not be
    read as one reporting a permanently still scene."""
    gate = MotionGate()
    gate.evaluate("front_door", blank(0))
    result = gate.evaluate("front_door", with_blob(0.5), producer_hint=None)
    assert result.reason == "differenced"
    assert result.motion is True


def test_hinted_frames_still_update_the_reference():
    """So that when hints stop arriving, differencing resumes from a recent frame
    rather than treating the next one as a cold start."""
    gate = MotionGate()
    gate.evaluate("front_door", blank(0), producer_hint=True)
    result = gate.evaluate("front_door", blank(0))
    assert result.reason == "differenced", "not 'first-frame' — a reference existed"
    assert result.motion is False


def test_hints_can_be_distrusted():
    gate = MotionGate(trust_producer_hint=False)
    gate.evaluate("front_door", blank(0))
    result = gate.evaluate("front_door", with_blob(0.5), producer_hint=False)
    assert result.reason == "differenced"
    assert result.motion is True


def test_forget_drops_a_cameras_reference():
    gate = MotionGate()
    gate.evaluate("front_door", blank())
    gate.forget("front_door")
    assert gate.tracked_cameras == []
    assert gate.evaluate("front_door", blank()).reason == "first-frame"
