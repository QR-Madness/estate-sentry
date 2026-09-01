"""L1 — the motion gate.

The cheapest layer, and the one that decides how much the expensive ones cost.
Every frame it rejects is a detector inference that never runs, which on CPU-only
hardware is the difference between a pipeline that keeps up and one that does not.

Two ways a frame can be judged, in order:

1. **The producer's hint.** An edge agent with a PIR sensor, or a camera with
   built-in motion detection, already knows. `FrameRef.motion_detected` carries
   that. The specification explicitly allows using an existing MOTION sensor
   reading as the gate signal.
2. **Frame differencing.** When there is no hint (`motion_detected is None`),
   compare against the previous frame from that camera.

The `None` / `False` distinction matters more than it looks. `None` means "nobody
evaluated motion"; `False` means "evaluated, and there was none". If those were
collapsed into one boolean, every producer that omits the hint would be read as a
permanently still scene and the gate would discard the entire stream.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..constants import MOTION_AREA_FRACTION, MOTION_PIXEL_DELTA


@dataclass(frozen=True, slots=True)
class MotionResult:
    """Outcome of the gate, with enough context to explain itself.

    `reason` exists because "the pipeline processed nothing for an hour" is a
    question that gets asked, and answering it should not require a debugger.
    """

    motion: bool
    changed_fraction: float
    reason: str


class MotionGate:
    """Per-camera frame differencing against the previously seen frame.

    Holds one reference frame per camera. Deliberately a *rolling* reference
    rather than a long-lived background model: a background model is better at
    ignoring a swaying tree, but it also learns a parked car into the background
    and then stops reporting it. For a gate whose only job is "is anything
    happening", the simpler and more literal comparison is the safer failure.
    """

    def __init__(
        self,
        *,
        pixel_delta: int = MOTION_PIXEL_DELTA,
        area_fraction: float = MOTION_AREA_FRACTION,
        trust_producer_hint: bool = True,
    ) -> None:
        self._pixel_delta = pixel_delta
        self._area_fraction = area_fraction
        self._trust_producer_hint = trust_producer_hint
        self._previous: dict[str, np.ndarray] = {}

    def evaluate(
        self,
        camera_id: str,
        gray: np.ndarray,
        *,
        producer_hint: bool | None = None,
    ) -> MotionResult:
        """Decide whether `gray` (a 2-D grayscale frame) warrants further work."""
        if producer_hint is not None and self._trust_producer_hint:
            # Still record the frame, so that when hints stop arriving the
            # differencing path has a recent reference instead of treating the
            # next frame as a cold start.
            self._previous[camera_id] = gray
            return MotionResult(
                motion=producer_hint,
                changed_fraction=0.0,
                reason="producer-hint",
            )

        previous = self._previous.get(camera_id)
        self._previous[camera_id] = gray

        if previous is None:
            # Nothing to compare against. Pass it through rather than drop it:
            # the first frame after a restart is exactly when something may be
            # happening, and a false negative there is worse than one inference.
            return MotionResult(True, 0.0, "first-frame")

        if previous.shape != gray.shape:
            # A resolution change makes the difference meaningless. Treat it as
            # motion and reset, rather than comparing incomparable arrays.
            return MotionResult(True, 0.0, "resolution-changed")

        diff = np.abs(gray.astype(np.int16) - previous.astype(np.int16))
        changed = int(np.count_nonzero(diff >= self._pixel_delta))
        fraction = changed / gray.size

        return MotionResult(
            motion=fraction >= self._area_fraction,
            changed_fraction=fraction,
            reason="differenced",
        )

    def forget(self, camera_id: str) -> None:
        """Drop a camera's reference frame, e.g. when it goes offline."""
        self._previous.pop(camera_id, None)

    @property
    def tracked_cameras(self) -> list[str]:
        return list(self._previous)
