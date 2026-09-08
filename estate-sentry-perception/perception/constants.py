"""Tunable constants for the perception service.

Values live here rather than scattered through the modules so there is one place
to look when behaviour under load needs adjusting. Where a number is not obvious,
the comment records *why* it is what it is — a convention borrowed from AgentX's
streaming constants, where the reasoning turned out to be worth more than the
value itself.
"""

from __future__ import annotations

import os

# =============================================================================
# Ring buffer / fan-out
# =============================================================================

#: Entries retained for reconnect catch-up via `snapshot(since_id=...)`.
#: Sized for "a viewer's connection blipped", not "a viewer was away for an
#: hour" — anything longer should be served from the object store, not RAM.
RING_HISTORY = 300

#: Per-subscriber queue depth before the oldest entry is evicted. At the default
#: 5 fps this is roughly four seconds of slack, which absorbs a GC pause or a
#: backgrounded tab without letting a genuinely dead client accumulate frames.
RING_SUBSCRIBER_QUEUE_MAX = 20

#: Concurrent live subscribers. Each one costs a queue, so this is a memory
#: ceiling as much as a policy: without it, opening tabs is a way to exhaust the
#: host. AgentX uses 32 for log streams; frames are heavier, so this is lower.
RING_MAX_SUBSCRIBERS = 16

#: Inbound frame queue for a consumer that does slow work — the pipeline itself.
#: Deliberately tiny, and for a different reason than the ring sizes above.
#:
#: Detection runs at roughly 2.4 fps on CPU against a producer sending 5. Any
#: depth here fills with frames the pipeline cannot reach in time, so it ends up
#: analysing footage from seconds ago and reporting it against a live view —
#: observed as detection boxes visibly trailing the video by several seconds.
#: The queue was doing exactly what it was told; the depth was wrong for this
#: consumer.
#:
#: At depth 2 the pipeline always works on a nearly-current frame and discards
#: the rest, so the only remaining lag is inference itself. For a live monitor
#: that is the right trade: a detection on the frame you are looking at beats a
#: complete record of frames you are not.
PIPELINE_INPUT_QUEUE_MAX = 2

# =============================================================================
# Capture
# =============================================================================

#: Frames per second a producer emits by default. The pipeline does not need
#: real time — detection at a few fps is ample for a driveway, and every frame
#: above that is inference cost for footage nobody will look at.
DEFAULT_CAPTURE_FPS = 5.0

#: JPEG quality for stored frames. 85 is the usual visually-lossless knee;
#: below ~75 compression artefacts start to affect detector confidence.
JPEG_QUALITY = 85

# =============================================================================
# Dead-air watchdog
# =============================================================================

#: Seconds without a frame before the pipeline emits a status event.
#: Silence is otherwise indistinguishable from a healthy but quiet camera, and
#: that ambiguity is precisely what makes a stalled capture loop hard to notice.
WATCHDOG_SILENCE_SECONDS = 10.0

#: How often to re-emit while silence continues, so a dashboard opened *during*
#: an outage still learns about it rather than waiting for the next transition.
WATCHDOG_REPEAT_SECONDS = 30.0

# =============================================================================
# L1 — motion gate
# =============================================================================

#: Per-pixel absolute difference (0-255) counted as changed. Low enough to catch
#: a person in poor light, high enough to ignore sensor noise and JPEG ringing.
MOTION_PIXEL_DELTA = 25

#: Fraction of changed pixels before a frame is considered to contain motion.
#: 0.2% of a 1080p frame is about 4,000 pixels — roughly a person at some
#: distance. Raising this trades missed approaches for fewer wind-in-trees wakeups.
MOTION_AREA_FRACTION = 0.002

# =============================================================================
# L2 — object detection
# =============================================================================

#: Apache-2.0, unlike ultralytics/YOLOv8 (AGPL-3.0), which would conflict with
#: this project's MIT licence. The r18vd backbone is the small variant, chosen
#: because inference here runs on CPU.
DETECTOR_MODEL = "PekingU/rtdetr_v2_r18vd"

#: Detections below this score are discarded before they reach zone logic.
#: Raised from 0.5 after watching real footage: the 0.50-0.62 band was almost
#: entirely spurious people in low light, and every one of them would have been
#: logged as a zone event. Env-tunable because the right value depends on the
#: camera and the scene, and finding it should not need a code change.
DETECTION_CONFIDENCE_THRESHOLD = float(
    os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.60")
)

#: Which point on a detection is tested against a zone polygon: "ground"
#: (bottom-centre, where the object meets the floor) or "centre".
#: Ground is the default because perimeters are drawn on the floor of a scene.
ZONE_ANCHOR = os.environ.get("ZONE_ANCHOR", "ground")

#: COCO classes worth acting on. The spec's taxonomy is person / vehicle /
#: animal / unknown, and this is the mapping onto what the model actually emits.
CLASSES_OF_INTEREST = {
    "person": "person",
    "bicycle": "vehicle",
    "car": "vehicle",
    "motorcycle": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
    "cat": "animal",
    "dog": "animal",
    "bird": "animal",
    "horse": "animal",
}
