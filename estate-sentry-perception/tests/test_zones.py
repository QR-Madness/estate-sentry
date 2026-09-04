"""L3 zone intersection.

Point-in-polygon is short enough to look obviously correct and subtle enough to
be wrong at the edges, so the awkward cases are pinned explicitly: concave
shapes, vertices level with the ray, and points outside a bounding box that a
naive implementation would still call inside.
"""

from __future__ import annotations

import pytest

from perception.pipeline.zones import (
    Perimeter,
    ZoneIndex,
    point_in_polygon,
)

# A unit square, and an L-shape that is deliberately concave.
SQUARE = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
L_SHAPE = [(0.0, 0.0), (0.6, 0.0), (0.6, 0.4), (1.0, 0.4), (1.0, 1.0), (0.0, 1.0)]


class TestPointInPolygon:
    @pytest.mark.parametrize(
        ("point", "expected"),
        [
            ((0.5, 0.5), True),    # centre
            ((0.25, 0.25), True),  # near a corner, inside
            ((0.1, 0.5), False),   # left of it
            ((0.9, 0.5), False),   # right of it
            ((0.5, 0.1), False),   # above it
            ((0.5, 0.9), False),   # below it
            ((0.0, 0.0), False),   # far outside
        ],
    )
    def test_square(self, point, expected):
        assert point_in_polygon(point, SQUARE) is expected

    def test_concave_shape_excludes_its_notch(self):
        """The case a bounding-box check gets wrong. (0.8, 0.2) sits inside the
        L's bounding box but in the cut-out corner, so it must be outside."""
        assert point_in_polygon((0.3, 0.2), L_SHAPE) is True
        assert point_in_polygon((0.8, 0.2), L_SHAPE) is False
        assert point_in_polygon((0.8, 0.7), L_SHAPE) is True

    def test_a_vertex_level_with_the_ray_is_not_counted_twice(self):
        """Two edges meet at y=0.5 here. Counting that crossing twice would flip
        the result back to 'outside' — the classic ray-casting bug."""
        diamond = [(0.5, 0.2), (0.8, 0.5), (0.5, 0.8), (0.2, 0.5)]
        assert point_in_polygon((0.5, 0.5), diamond) is True

    @pytest.mark.parametrize("polygon", [[], [(0.1, 0.1)], [(0.1, 0.1), (0.2, 0.2)]])
    def test_degenerate_polygons_contain_nothing(self, polygon):
        """Fewer than three points is not a shape. Returning False beats raising:
        one bad perimeter should not take down the frame."""
        assert point_in_polygon((0.15, 0.15), polygon) is False


def perimeter(zone_name="front path", camera="passageway", polygon=None):
    return Perimeter(
        zone_id="11111111-1111-1111-1111-111111111111",
        zone_name=zone_name,
        camera_pk=1,
        camera_name=camera,
        polygon=polygon or SQUARE,
    )


class TestZoneIndex:
    def test_pixel_centroids_are_normalised_against_the_frame(self):
        """Perimeters are 0-1 and detections are pixels; the conversion is the
        whole reason a resolution change does not invalidate every polygon."""
        index = ZoneIndex([perimeter()])
        # (320, 240) of a 640x480 frame is the centre, inside the square.
        assert [m.zone_name for m in index.matches("passageway", (320, 240), (640, 480))] == [
            "front path"
        ]
        # The same pixel in a 1920x1080 frame is up and left, outside it.
        assert index.matches("passageway", (320, 240), (1920, 1080)) == []

    def test_a_detection_can_match_several_overlapping_zones(self):
        """A doorway may legitimately belong to both 'porch' and 'entry', each
        with its own rules. Returning only the first would silently drop one."""
        index = ZoneIndex([
            perimeter(zone_name="porch"),
            perimeter(zone_name="entry", polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]),
        ])
        names = {m.zone_name for m in index.matches("passageway", (320, 240), (640, 480))}
        assert names == {"porch", "entry"}

    def test_cameras_are_isolated_from_each_other(self):
        index = ZoneIndex([perimeter(camera="passageway")])
        assert index.matches("driveway", (320, 240), (640, 480)) == []
        assert index.has_coverage("passageway") is True
        assert index.has_coverage("driveway") is False

    def test_an_empty_index_matches_nothing_without_raising(self):
        """The state on a fresh install, or when the API is unreachable. The
        pipeline must keep detecting; it just cannot say where."""
        index = ZoneIndex()
        assert len(index) == 0
        assert index.matches("passageway", (320, 240), (640, 480)) == []

    @pytest.mark.parametrize("size", [(0, 480), (640, 0), (0, 0)])
    def test_a_degenerate_frame_size_does_not_divide_by_zero(self, size):
        index = ZoneIndex([perimeter()])
        assert index.matches("passageway", (10, 10), size) == []

    def test_cameras_lists_what_has_coverage(self):
        index = ZoneIndex([perimeter(camera="driveway"), perimeter(camera="passageway")])
        assert index.cameras == ["driveway", "passageway"]
