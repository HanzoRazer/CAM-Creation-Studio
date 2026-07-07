import math

import pytest

from cam_creation_studio.shared.geometry import (
    Bounds,
    Point,
    arc_length,
    arc_points,
    bounds,
    bounds_from_points,
    distance,
    distance_2d,
    distance_3d,
    interpolate_arc,
)


def test_distance_3d():
    assert distance(Point(0, 0, 0), Point(3, 4, 0)) == 5.0
    assert distance(Point(0, 0, 0), Point(0, 0, 2)) == 2.0
    assert Point(1, 1).distance_to(Point(1, 1)) == 0.0


def test_arc_length():
    # quarter circle of radius 2
    assert arc_length(2.0, math.pi / 2) == pytest.approx(math.pi)
    # sign of sweep does not affect length
    assert arc_length(2.0, -math.pi / 2) == pytest.approx(math.pi)


def test_bounds_over_points():
    b = bounds([Point(1, 2, 0), Point(-3, 5, 4), Point(0, 0, -1)])
    assert b == Bounds(-3, 0, 1, 5, -1, 4)
    assert b.width == 4 and b.height == 5 and b.depth == 5
    assert b.as_tuple() == (-3, 0, 1, 5)


def test_bounds_empty_is_none():
    assert bounds([]) is None


def test_bounds_center():
    assert bounds([Point(0, 0), Point(10, 20)]).center == Point(5.0, 10.0, 0.0)


def test_interpolate_arc_endpoints_and_radius():
    # Semicircle: start (10,0), center (0,0) via i=-10, end (-10,0), CCW.
    start, end = Point(10, 0), Point(-10, 0)
    pts = interpolate_arc(start, end, i=-10, j=0, clockwise=False, segments=8)
    assert pts[0] == start
    assert pts[-1].x == pytest.approx(-10) and pts[-1].y == pytest.approx(0, abs=1e-9)
    assert len(pts) == 9  # start + 8 subdivisions
    # every interpolated point lies on the radius-10 circle about the origin
    for p in pts:
        assert math.hypot(p.x, p.y) == pytest.approx(10.0, abs=1e-9)


def test_interpolate_arc_z_lerps():
    pts = interpolate_arc(Point(10, 0, 0), Point(0, 10, 5), i=-10, j=0,
                          clockwise=False, segments=4)
    assert pts[0].z == 0.0
    assert pts[-1].z == pytest.approx(5.0)
    assert pts[2].z == pytest.approx(2.5)  # halfway


# ---- CS-003 canonical name aliases ----
def test_distance_3d_alias():
    assert distance_3d is distance
    assert distance_3d(Point(0, 0, 0), Point(3, 4, 0)) == 5.0


def test_distance_2d_ignores_z():
    # z difference does not affect the planar distance
    assert distance_2d(Point(0, 0, 100), Point(3, 4, -50)) == 5.0


def test_bounds_from_points_alias():
    assert bounds_from_points is bounds
    assert bounds_from_points([Point(0, 0), Point(2, 3)]).as_tuple() == (0, 0, 2, 3)


def test_arc_points_alias():
    assert arc_points is interpolate_arc
    pts = arc_points(Point(10, 0), Point(-10, 0), i=-10, j=0, clockwise=False, segments=8)
    assert pts[0] == Point(10, 0) and len(pts) == 9
