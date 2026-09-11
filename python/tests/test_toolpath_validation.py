"""Structural validation of controller-neutral toolpaths (CS-016)."""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import (
    make_arc_motion,
    make_linear_motion,
    make_operation_path,
    make_toolpath_plan,
)
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.errors import ToolpathError
from cam_creation_studio.toolpath.models import (
    TOOLPATH_PLAN_V1,
    LinearMotion,
    OperationPath,
    ToolpathPlan,
    ToolpathStrategy,
)
from cam_creation_studio.toolpath.validation import validate_toolpath_plan


def _strategy() -> ToolpathStrategy:
    return ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="demo")


def _cut(start: Point, end: Point, *, index: int, **kwargs) -> LinearMotion:
    return make_linear_motion(
        MotionKind.CUT, start, end, index=index,
        planned_feed_mm_min=800.0, geometry_ids=("geom-a",), **kwargs)


def _plan_from_paths(*paths: OperationPath, **kwargs) -> ToolpathPlan:
    defaults = dict(
        operation_definition_id="def-1",
        geometry_ids=("geom-a",),
        binding_id="bind-1",
        strategy=_strategy(),
        paths=paths,
        geometry_digest="geo-v1",
        definition_digest="def-v1",
        recommendation_digest="rec-v1",
        recommendation_id="rec-1",
        planned_feed_mm_min=800.0,
        tool_diameter_mm=6.35,
        tool_flutes=2,
        material_id="hardwood",
        material_chipload_mm=(0.04, 0.10),
    )
    defaults.update(kwargs)
    return make_toolpath_plan(**defaults)


def test_continuous_path_validates():
    motions = (
        make_linear_motion(
            MotionKind.TRAVEL, Point(0, 0, 5), Point(0, 0, 0), index=0),
        _cut(Point(0, 0, 0), Point(20, 0, 0), index=1),
        make_linear_motion(
            MotionKind.RETRACT, Point(20, 0, 0), Point(20, 0, 5), index=2),
    )
    plan = _plan_from_paths(make_operation_path(motions, existing_count=0))
    validate_toolpath_plan(plan)


def test_empty_paths_fail_closed():
    with pytest.raises(ToolpathError, match="at least one path"):
        _plan_from_paths()


def test_empty_motions_fail_closed():
    with pytest.raises(ToolpathError, match="must contain motions"):
        _plan_from_paths(OperationPath(id="path-1", motions=()))


def test_discontinuous_motions_must_be_split():
    motions = (
        _cut(Point(0, 0, 0), Point(10, 0, 0), index=0),
        _cut(Point(20, 0, 0), Point(30, 0, 0), index=1),
    )
    with pytest.raises(ToolpathError, match="discontinuous"):
        _plan_from_paths(make_operation_path(motions, existing_count=0))


def test_discontinuous_work_as_separate_paths():
    first = make_operation_path(
        (_cut(Point(0, 0, 0), Point(10, 0, 0), index=0),), existing_count=0)
    second = make_operation_path(
        (_cut(Point(20, 0, 0), Point(30, 0, 0), index=1),), existing_count=1)
    plan = _plan_from_paths(first, second)
    assert len(plan.paths) == 2


def test_zero_length_linear_is_rejected():
    with pytest.raises(ToolpathError, match="coincident start and end"):
        _plan_from_paths(make_operation_path(
            (_cut(Point(1, 1, 0), Point(1, 1, 0), index=0),),
            existing_count=0))


def test_non_finite_coordinates_are_rejected():
    with pytest.raises(ToolpathError, match="finite"):
        _plan_from_paths(make_operation_path(
            (_cut(Point(0, 0, 0), Point(math.inf, 0, 0), index=0),),
            existing_count=0))


def test_feed_must_be_positive_when_supplied():
    with pytest.raises(ToolpathError, match="greater than 0"):
        _plan_from_paths(
            make_operation_path(
                (make_linear_motion(
                    MotionKind.CUT, Point(0, 0, 0), Point(10, 0, 0),
                    index=0, planned_feed_mm_min=0.0),),
                existing_count=0))


def test_travel_may_omit_feed():
    travel = make_linear_motion(
        MotionKind.TRAVEL, Point(0, 0, 5), Point(10, 0, 5), index=0)
    plan = _plan_from_paths(make_operation_path((travel,), existing_count=0))
    assert plan.paths[0].motions[0].planned_feed_mm_min is None


def test_missing_binding_id_is_rejected():
    path = make_operation_path(
        (_cut(Point(0, 0, 0), Point(10, 0, 0), index=0),), existing_count=0)
    plan = ToolpathPlan(
        id="tp-1",
        version=TOOLPATH_PLAN_V1,
        operation_definition_id="def-1",
        geometry_ids=("geom-a",),
        binding_id="",
        strategy_fingerprint="strat-x",
        upstream_fingerprint="up-x",
        paths=(path,),
    )
    with pytest.raises(ToolpathError, match="binding_id"):
        validate_toolpath_plan(plan)


def test_duplicate_motion_ids_are_rejected():
    a = _cut(Point(0, 0, 0), Point(10, 0, 0), index=0, id="dup")
    b = _cut(Point(10, 0, 0), Point(20, 0, 0), index=1, id="dup")
    with pytest.raises(ToolpathError, match="duplicate motion"):
        _plan_from_paths(make_operation_path((a, b), existing_count=0, id="p1"))


def test_per_motion_geometry_must_be_a_subset():
    motion = make_linear_motion(
        MotionKind.CUT, Point(0, 0, 0), Point(10, 0, 0), index=0,
        planned_feed_mm_min=800.0, geometry_ids=("geom-other",))
    with pytest.raises(ToolpathError, match="not a subset"):
        _plan_from_paths(make_operation_path((motion,), existing_count=0))


def test_empty_per_motion_geometry_inherits_plan_level():
    motion = make_linear_motion(
        MotionKind.CUT, Point(0, 0, 0), Point(10, 0, 0), index=0,
        planned_feed_mm_min=800.0, geometry_ids=())
    plan = _plan_from_paths(make_operation_path((motion,), existing_count=0))
    assert plan.paths[0].motions[0].geometry_ids == ()
    assert plan.geometry_ids == ("geom-a",)
