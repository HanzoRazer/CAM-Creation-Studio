"""Canonical toolpath dataclasses (CS-016).

Pins frozen/slotted contracts and closed vocabularies. Construction helpers
and validation live in later modules.
"""

from __future__ import annotations

import dataclasses

import pytest

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.enums import MotionKind, ToolpathStatus
from cam_creation_studio.toolpath.errors import ToolpathError
from cam_creation_studio.toolpath.models import (
    TOOLPATH_PLAN_V1,
    ArcMotion,
    LinearMotion,
    OperationPath,
    ToolpathPlan,
    ToolpathStrategy,
)


def _linear(**kwargs) -> LinearMotion:
    defaults = dict(
        id="lin-1",
        kind=MotionKind.CUT,
        start=Point(0, 0, 0),
        end=Point(10, 0, 0),
    )
    defaults.update(kwargs)
    return LinearMotion(**defaults)


def test_core_dataclasses_are_frozen_and_slotted():
    for cls in (
        ToolpathStrategy, LinearMotion, ArcMotion, OperationPath, ToolpathPlan,
    ):
        assert cls.__dataclass_params__.frozen
        assert getattr(cls, "__slots__", ())


def test_linear_equality_is_by_value():
    a = _linear()
    b = _linear()
    assert a == b
    assert a != _linear(end=Point(11, 0, 0))


def test_mutation_is_rejected():
    motion = _linear()
    with pytest.raises(dataclasses.FrozenInstanceError):
        motion.kind = MotionKind.TRAVEL  # type: ignore[misc]


def test_motion_kind_has_four_planning_values():
    assert {k.value for k in MotionKind} == {
        "travel", "cut", "plunge", "retract",
    }


def test_status_is_structural_not_safety():
    assert {s.value for s in ToolpathStatus} == {
        "missing", "current", "stale",
    }
    assert "safe" not in {s.value for s in ToolpathStatus}


def test_kind_string_coerces_to_enum():
    motion = _linear(kind="plunge")
    assert motion.kind is MotionKind.PLUNGE


def test_travel_may_omit_feed_cut_may_carry_planned_feed():
    travel = _linear(kind=MotionKind.TRAVEL, planned_feed_mm_min=None)
    cut = _linear(kind=MotionKind.CUT, planned_feed_mm_min=800.0)
    assert travel.planned_feed_mm_min is None
    assert cut.planned_feed_mm_min == 800.0


def test_plunge_and_retract_are_kinds_not_z_sign():
    z = -3.0
    plunge = _linear(
        kind=MotionKind.PLUNGE, start=Point(4, 0, 5), end=Point(4, 0, z),
    )
    retract = _linear(
        kind=MotionKind.RETRACT, start=Point(4, 0, z), end=Point(4, 0, 5),
    )
    assert plunge.kind is not retract.kind
    assert plunge.end.z == retract.start.z


def test_arc_stores_analytic_fields():
    arc = ArcMotion(
        id="arc-1",
        kind=MotionKind.CUT,
        start=Point(10, 0, 0),
        end=Point(0, 10, 0),
        center=Point(0, 0, 0),
        radius=10.0,
        clockwise=False,
        sweep_rad=1.5707963267948966,
    )
    assert arc.center == Point(0, 0, 0)
    assert arc.radius == 10.0
    assert arc.clockwise is False
    assert arc.sweep_rad > 0


def test_full_circle_is_coincident_endpoints_plus_full_sweep():
    start = Point(10, 0, 0)
    arc = ArcMotion(
        id="arc-full",
        kind=MotionKind.CUT,
        start=start,
        end=start,
        center=Point(0, 0, 0),
        radius=10.0,
        clockwise=False,
        sweep_rad=6.283185307179586,
    )
    assert arc.start == arc.end
    assert abs(arc.sweep_rad) > 6.0


def test_operation_path_preserves_motion_order():
    motions = (
        _linear(id="a", kind=MotionKind.TRAVEL),
        _linear(id="b", kind=MotionKind.CUT, start=Point(10, 0, 0),
                end=Point(20, 0, 0)),
    )
    path = OperationPath(id="path-1", motions=motions, depth_mm=3.0)
    assert [m.id for m in path.motions] == ["a", "b"]
    assert path.depth_mm == 3.0


def test_plan_holds_lineage_without_copying_upstream_objects():
    path = OperationPath(id="path-1", motions=(_linear(),), depth_mm=None)
    plan = ToolpathPlan(
        id="tp-1",
        version=TOOLPATH_PLAN_V1,
        operation_definition_id="def-1",
        geometry_ids=("geom-a", "geom-b"),
        binding_id="bind-1",
        strategy_fingerprint="strat-x",
        upstream_fingerprint="up-x",
        paths=(path,),
        recommendation_id="rec-1",
        planned_feed_mm_min=1800.0,
    )
    assert plan.operation_definition_id == "def-1"
    assert plan.binding_id == "bind-1"
    assert plan.geometry_ids == ("geom-a", "geom-b")
    assert plan.recommendation_id == "rec-1"
    assert plan.planned_feed_mm_min == 1800.0
    assert "Line2D" not in plan.__dataclass_fields__


def test_recommendation_id_is_optional():
    path = OperationPath(id="path-1", motions=(_linear(),))
    plan = ToolpathPlan(
        id="tp-1",
        version=TOOLPATH_PLAN_V1,
        operation_definition_id="def-1",
        geometry_ids=("geom-a",),
        binding_id="bind-1",
        strategy_fingerprint="strat-x",
        upstream_fingerprint="up-x",
        paths=(path,),
        recommendation_id=None,
        planned_feed_mm_min=650.0,
    )
    assert plan.recommendation_id is None
    assert plan.planned_feed_mm_min == 650.0


def test_strategy_label_is_presentation_only_on_the_object():
    a = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="a")
    b = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="b")
    assert a.travel_height_mm == b.travel_height_mm
    assert a.label != b.label


def test_toolpath_error_is_a_valueerror():
    assert issubclass(ToolpathError, ValueError)
    with pytest.raises(ToolpathError):
        raise ToolpathError("broken")


def test_models_have_no_preview_or_gcode_fields():
    forbidden = {
        "source_command", "MoveType", "dialect", "controller",
        "postprocessor", "machine_ready", "approved", "feed_mm_min",
        "role", "source_fingerprint",
    }
    for cls in (LinearMotion, ArcMotion, OperationPath, ToolpathPlan,
                ToolpathStrategy):
        names = set(cls.__dataclass_fields__)
        assert not (names & forbidden), (cls, names & forbidden)
