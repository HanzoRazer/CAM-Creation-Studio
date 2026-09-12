"""Analytic arc contracts for controller-neutral toolpaths (CS-016)."""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import (
    make_arc_motion,
    make_operation_path,
    make_toolpath_plan,
)
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.errors import ToolpathError
from cam_creation_studio.toolpath.models import ArcMotion, ToolpathStrategy
from cam_creation_studio.toolpath.validation import signed_sweep


def _plan_with(arc: ArcMotion):
    return make_toolpath_plan(
        operation_definition_id="def-1",
        geometry_ids=("geom-a",),
        binding_id="bind-1",
        strategy=ToolpathStrategy(travel_height_mm=5.0),
        paths=(make_operation_path((arc,), existing_count=0),),
        geometry_digest="geo-v1",
        definition_digest="def-v1",
        planned_feed_mm_min=400.0,
        material_id="hardwood",
    )


def test_make_arc_computes_radius_and_quarter_sweep():
    arc = make_arc_motion(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), False,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    assert arc.radius == pytest.approx(10.0)
    assert arc.clockwise is False
    assert arc.sweep_rad == pytest.approx(math.pi / 2)
    _plan_with(arc)


def test_clockwise_quarter_is_the_long_way_around():
    arc = make_arc_motion(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), True,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    assert arc.sweep_rad == pytest.approx(-3 * math.pi / 2)
    assert arc.clockwise is True
    _plan_with(arc)


def test_full_circle_is_coincident_endpoints_with_two_pi_sweep():
    start = Point(10, 0, -3)
    arc = make_arc_motion(
        start, start, Point(0, 0, -3), False,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    assert arc.start == arc.end
    assert arc.sweep_rad == pytest.approx(2 * math.pi)
    _plan_with(arc)


def test_clockwise_full_circle_has_negative_sweep():
    start = Point(10, 0, 0)
    arc = make_arc_motion(
        start, start, Point(0, 0, 0), True,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    assert arc.sweep_rad == pytest.approx(-2 * math.pi)
    _plan_with(arc)


def test_zero_length_arc_is_rejected():
    arc = ArcMotion(
        id="arc-zero",
        kind=MotionKind.CUT,
        start=Point(10, 0, 0),
        end=Point(10, 0, 0),
        center=Point(0, 0, 0),
        radius=10.0,
        clockwise=False,
        sweep_rad=0.0,
        planned_feed_mm_min=400.0,
        geometry_ids=("geom-a",),
    )
    with pytest.raises(ToolpathError, match="full turn"):
        _plan_with(arc)


def test_radius_must_be_positive():
    arc = ArcMotion(
        id="arc-r0",
        kind=MotionKind.CUT,
        start=Point(0, 0, 0),
        end=Point(1, 0, 0),
        center=Point(0, 0, 0),
        radius=0.0,
        clockwise=False,
        sweep_rad=1.0,
        planned_feed_mm_min=400.0,
        geometry_ids=("geom-a",),
    )
    with pytest.raises(ToolpathError, match="radius"):
        _plan_with(arc)


def test_inconsistent_center_is_rejected():
    arc = make_arc_motion(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), False,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    broken = ArcMotion(
        id=arc.id, kind=arc.kind, start=arc.start, end=arc.end,
        center=Point(1, 0, 0), radius=arc.radius, clockwise=False,
        sweep_rad=arc.sweep_rad, planned_feed_mm_min=400.0,
        geometry_ids=("geom-a",),
    )
    with pytest.raises(ToolpathError, match="inconsistent"):
        _plan_with(broken)


def test_clockwise_flag_must_match_signed_sweep():
    arc = make_arc_motion(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), False,
        index=0, planned_feed_mm_min=400.0, geometry_ids=("geom-a",),
    )
    broken = ArcMotion(
        id=arc.id, kind=arc.kind, start=arc.start, end=arc.end,
        center=arc.center, radius=arc.radius, clockwise=True,
        sweep_rad=arc.sweep_rad, planned_feed_mm_min=400.0,
        geometry_ids=("geom-a",),
    )
    with pytest.raises(ToolpathError, match="clockwise"):
        _plan_with(broken)


def test_signed_sweep_matches_shared_geometry_convention():
    start, end, center = Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0)
    assert signed_sweep(start, end, center, False) == pytest.approx(math.pi / 2)
    assert signed_sweep(start, end, center, True) == pytest.approx(-3 * math.pi / 2)
    assert signed_sweep(start, start, center, False) == pytest.approx(2 * math.pi)
