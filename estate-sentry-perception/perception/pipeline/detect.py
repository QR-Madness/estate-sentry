"""L2 — object detection.

The concrete model sits behind the `Detector` protocol for two reasons, both of
which are live concerns rather than speculative ones:

* **Licensing.** The specification names YOLO, but ultralytics/YOLOv8 is AGPL-3.0
  and Estate Sentry is MIT. The default here is RT-DETRv2 (Apache-2.0), which the
  specification lists as an equal option. If that calculus ever changes, it
  should be one class, not a rewrite.
* **Weight.** `transformers` plus `torch` is multiple gigabytes and the machine
  has no discrete GPU. Anything that wants to exercise the pipeline without
  paying for that — the test suite, a laptop, CI — uses `StubDetector`.

Detections are reported with both the model's own label and the specification's
coarser taxonomy (person / vehicle / animal), because downstream zone rules are
written against the taxonomy while debugging needs the raw label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..constants import (
    CLASSES_OF_INTEREST,
    DETECTION_CONFIDENCE_THRESHOLD,
    DETECTOR_MODEL,
)

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


@dataclass(frozen=True, slots=True)
class Detection:
    """One detected object, in pixel coordinates of the source frame."""

    label: str
    category: str
    confidence: float
    #: (x1, y1, x2, y2), top-left origin.
    box: tuple[float, float, float, float]

    @property
    def centroid(self) -> tuple[float, float]:
        """Point used for zone intersection at L3.

        The centroid of the whole box, not the base of it. That is a real
        simplification: for a person, the point that actually sits inside a
        ground-plane zone is roughly the feet, and the box centre floats at
        chest height. It is left simple until zones exist to test against.
        """
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2, (y1 + y2) / 2)


@runtime_checkable
class Detector(Protocol):
    """Anything that can turn a frame into detections."""

    def detect(self, image: np.ndarray) -> list[Detection]: ...


def categorise(label: str) -> str | None:
    """Map a model label onto the specification's taxonomy, or None to discard."""
    return CLASSES_OF_INTEREST.get(label.lower())


class StubDetector(Detector):
    """Returns a canned result. Lets the pipeline be tested without torch."""

    def __init__(self, detections: list[Detection] | None = None) -> None:
        self.detections = detections or []
        self.calls = 0

    def detect(self, image: np.ndarray) -> list[Detection]:
        self.calls += 1
        return list(self.detections)


class RTDetrDetector(Detector):
    """RT-DETRv2 via `transformers` (Apache-2.0), running on CPU.

    Model and processor load on first use rather than at construction, so
    importing this module — which the service does unconditionally — does not
    pull a multi-gigabyte tensor stack into a process that may only ever run the
    motion gate.
    """

    def __init__(
        self,
        model_name: str = DETECTOR_MODEL,
        *,
        confidence_threshold: float = DETECTION_CONFIDENCE_THRESHOLD,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._model = None
        self._processor = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import RTDetrImageProcessor, RTDetrV2ForObjectDetection
        except ImportError as exc:  # pragma: no cover — depends on optional extra
            raise ImportError(
                "RTDetrDetector needs the 'detect' extra: uv sync --extra detect"
            ) from exc

        self._processor = RTDetrImageProcessor.from_pretrained(self.model_name)
        self._model = RTDetrV2ForObjectDetection.from_pretrained(self.model_name).to(
            self.device
        )
        self._model.eval()

    def detect(self, image: np.ndarray) -> list[Detection]:
        import torch

        self._ensure_loaded()
        assert self._model is not None and self._processor is not None

        height, width = image.shape[:2]
        inputs = self._processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self._model(**inputs)

        results = self._processor.post_process_object_detection(
            outputs,
            target_sizes=torch.tensor([(height, width)]),
            threshold=self.confidence_threshold,
        )[0]

        detections: list[Detection] = []
        for score, label_id, box in zip(
            results["scores"], results["labels"], results["boxes"], strict=True
        ):
            label = self._model.config.id2label[label_id.item()]
            category = categorise(label)
            if category is None:
                # A detected sofa is not a security event. Filtering here keeps
                # the noise out of zone logging entirely.
                continue
            x1, y1, x2, y2 = (round(v, 2) for v in box.tolist())
            detections.append(
                Detection(
                    label=label,
                    category=category,
                    confidence=round(score.item(), 4),
                    box=(x1, y1, x2, y2),
                )
            )
        return detections
