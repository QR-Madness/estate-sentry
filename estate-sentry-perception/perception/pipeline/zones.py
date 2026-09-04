"""L3 — zone intersection.

Turns "a person at pixel (312, 208) on camera *passageway*" into "a person in
the *front path* zone", which is the first point in the pipeline where a
detection becomes something a person can reason about.

Two conventions make this work across cameras:

* **Perimeters are normalised to 0-1**, not pixels, so a resolution change or a
  lower-quality stream does not invalidate every polygon drawn against a camera.
  Detections arrive in pixels and are normalised here.
* **A detection is located by one point**, its box centroid, tested against each
  polygon. Simple, and honest about its limitation: for a person, the point
  actually standing on the ground is roughly the feet, while the box centre
  floats around chest height. Near a zone boundary that difference decides the
  answer. Left as-is until there are real perimeters to calibrate against —
  see `Detection.centroid`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

Point = tuple[float, float]
Polygon = list[Point]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray casting: count crossings of a ray from the point to +x.

    Odd crossings means inside. Handles concave shapes, which matters because a
    real perimeter — a path bending around a building — is rarely convex.

    Points exactly on an edge are not guaranteed either way; that ambiguity is
    inherent to the method and irrelevant at the precision perimeters are drawn.
    """
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False
    j = len(polygon) - 1

    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        # Does the edge straddle the ray's y? The asymmetric comparison
        # (one strict, one not) is what stops a vertex exactly level with the
        # ray from being counted twice.
        if (yi > y) != (yj > y):
            x_crossing = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_crossing:
                inside = not inside
        j = i

    return inside


@dataclass(frozen=True, slots=True)
class ZoneMatch:
    """A zone a detection fell inside."""

    zone_id: str
    zone_name: str
    camera_pk: int


@dataclass(frozen=True, slots=True)
class Perimeter:
    zone_id: str
    zone_name: str
    camera_pk: int
    camera_name: str
    polygon: Polygon


class ZoneIndex:
    """Camera-keyed perimeter lookup, built from the API and held in memory.

    Zones change rarely and are consulted on every detection, so this is fetched
    once at startup and cached rather than queried per frame.
    """

    def __init__(self, perimeters: list[Perimeter] | None = None) -> None:
        self._by_camera: dict[str, list[Perimeter]] = defaultdict(list)
        for perimeter in perimeters or []:
            self._by_camera[perimeter.camera_name].append(perimeter)

    @property
    def cameras(self) -> list[str]:
        return sorted(self._by_camera)

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_camera.values())

    def has_coverage(self, camera_name: str) -> bool:
        return bool(self._by_camera.get(camera_name))

    def matches(
        self,
        camera_name: str,
        centroid_px: Point,
        frame_size: tuple[int, int],
    ) -> list[ZoneMatch]:
        """Zones containing `centroid_px` on this camera.

        A list, not one zone: overlapping perimeters are legitimate — a doorway
        may reasonably belong to both "porch" and "entry", and each may carry
        different rules. Returning only the first would silently drop one.
        """
        perimeters = self._by_camera.get(camera_name)
        if not perimeters:
            return []

        width, height = frame_size
        if width <= 0 or height <= 0:
            logger.warning("%s: bad frame size %r", camera_name, frame_size)
            return []

        x, y = centroid_px[0] / width, centroid_px[1] / height

        return [
            ZoneMatch(p.zone_id, p.zone_name, p.camera_pk)
            for p in perimeters
            if point_in_polygon((x, y), p.polygon)
        ]
