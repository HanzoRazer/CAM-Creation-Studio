"""Preview projection of canonical planned motion (CS-016)."""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.preview.toolpath_model import (
    ARC,
    CUT,
    TRAVEL,
    ToolpathSegment,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import (
    make_arc_motion,
    make_linear_motion,
    make_operation_path,
    make_toolpath_plan,
)
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.models import ToolpathStrategy
from cam_creation_studio.toolpath.preview_adapter import (
    preview_projection_loss,
    toolpath_to_preview,
)


def _plan_with(*motions, **kwargs):
    defaults = dict(
        operation_definition_id="def-1",
        geometry_ids=("geom-a",),
        binding_id="bind-1",
        strategy=ToolpathStrategy(travel_height_mm=5.0),
        paths=(make_operation_path(motions, existing_count=0),),
        geometry_digest="geo-v1",
        definition_digest="def-v1",
        planned_feed_mm_min=800.0,
        material_id="hardwood",
    )
    defaults.update(kwargs)
    return make_toolpath_plan(**defaults)


def test_preview_uses_existing_toolpath_segment():
    motions = (
        make_linear_motion(
            MotionKind.TRAVEL, Point(0, 0, 5), Point(0, 0, 0), index=0),
        make_linear_motion(
            MotionKind.CUT, Point(0, 0, 0), Point(20, 0, 0), index=1,
            planned_feed_mm_min=800.0),
        make_linear_motion(
            MotionKind.RETRACT, Point(20, 0, 0), Point(20, 0, 5), index=2),
    )
    segs = toolpath_to_preview(_plan_with(*motions))
    assert segs and all(isinstance(s, ToolpathSegment) for s in segs)
    assert [s.type for s in segs] == [TRAVEL, CUT, TRAVEL]
    assert segs[1].end.x == 20
    assert all(s.source_command == "" for s in segs)
    assert segs[0].feed is None
    assert segs[2].feed is None
    assert segs[1].feed == 800.0


def test_plunge_projects_as_cut_and_retract_as_travel():
    motions = (
        make_linear_motion(
            MotionKind.PLUNGE, Point(4, 0, 5), Point(4, 0, -3), index=0,
            planned_feed_mm_min=300.0),
        make_linear_motion(
            MotionKind.RETRACT, Point(4, 0, -3), Point(4, 0, 5), index=1),
    )
    segs = toolpath_to_preview(_plan_with(*motions))
    assert [s.type for s in segs] == [CUT, TRAVEL]


def test_open_arc_projects_as_preview_arc_without_center():
    arc = make_arc_motion(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), False,
        index=0, planned_feed_mm_min=400.0)
    segs = toolpath_to_preview(_plan_with(arc))
    assert len(segs) == 1
    assert segs[0].type == ARC
    assert not hasattr(segs[0], "center")
    assert not hasattr(segs[0], "sweep_rad")
    assert segs[0].source_command == ""
    assert segs[0].distance == pytest.approx(10.0 * math.pi / 2)
    loss = preview_projection_loss()
    assert "arc center" in loss
    assert "plunge vs retract vs travel kinds" in loss


def test_full_circle_is_tessellated_in_preview_only():
    start = Point(10, 0, 0)
    arc = make_arc_motion(
        start, start, Point(0, 0, 0), False,
        index=0, planned_feed_mm_min=400.0)
    plan = _plan_with(arc)
    stored = plan.paths[0].motions[0]
    assert stored.start == stored.end
    assert stored.sweep_rad == pytest.approx(2 * math.pi)
    segs = toolpath_to_preview(plan)
    assert len(segs) > 1
    assert all(s.type == CUT for s in segs)
    assert segs[0].start.x == pytest.approx(10.0)
    assert segs[0].start.y == pytest.approx(0.0)
    assert plan.paths[0].motions[0].center == Point(0, 0, 0)
    assert plan.paths[0].motions[0].start == plan.paths[0].motions[0].end
    assert all(s.source_command == "" for s in segs)
    total = sum(s.distance for s in segs)
    assert total == pytest.approx(2 * math.pi * 10.0, rel=1e-3)
