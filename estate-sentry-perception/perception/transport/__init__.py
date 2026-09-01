"""Transport seam: frame storage and the message bus.

Import from here rather than the submodules, so swapping an implementation is a
one-line change at the composition root.
"""

from .memory import InMemoryEventBus, InMemoryFrameStore, subject_matches
from .protocols import (
    ALL_FRAMES_SUBJECT,
    EventBus,
    FrameRef,
    FrameStore,
    frame_key,
    frame_subject,
)

__all__ = [
    "ALL_FRAMES_SUBJECT",
    "EventBus",
    "FrameRef",
    "FrameStore",
    "InMemoryEventBus",
    "InMemoryFrameStore",
    "frame_key",
    "frame_subject",
    "subject_matches",
]
