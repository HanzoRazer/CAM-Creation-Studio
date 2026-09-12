"""Deterministic toolpath IDs and fingerprints (CS-016)."""

from __future__ import annotations

from dataclasses import replace

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.shared.ids import stable_id
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.fingerprint import (
    strategy_fingerprint,
    upstream_fingerprint,
)
from cam_creation_studio.toolpath.ids import (
    make_motion_id,
    make_operation_path_id,
    make_toolpath_id,
)
from cam_creation_studio.toolpath.models import ToolpathStrategy


def test_linear_motion_ids_are_stable():
    start, end = Point(0, 0, 5), Point(0, 0, 0)
    a = make_motion_id("linear", MotionKind.PLUNGE.value, start, end, index=0)
    b = make_motion_id("linear", MotionKind.PLUNGE.value, start, end, index=0)
    assert a == b
    assert a.startswith("lin-")
    assert a == stable_id(
        "linear", "plunge", 0, 0, 5, 0, 0, 0, 0, prefix="lin-")


def test_index_and_kind_change_motion_ids():
    start, end = Point(0, 0, 0), Point(10, 0, 0)
    base = make_motion_id("linear", "cut", start, end, index=0)
    assert make_motion_id("linear", "cut", start, end, index=1) != base
    assert make_motion_id("linear", "travel", start, end, index=0) != base


def test_arc_motion_ids_include_center_and_direction():
    start, end, center = Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0)
    ccw = make_motion_id(
        "arc", "cut", start, end, index=0, center=center, clockwise=False)
    cw = make_motion_id(
        "arc", "cut", start, end, index=0, center=center, clockwise=True)
    assert ccw != cw
    assert ccw.startswith("arc-")


def test_path_and_plan_ids_are_deterministic():
    path_a = make_operation_path_id("lin-1", "lin-2", existing_count=0)
    path_b = make_operation_path_id("lin-1", "lin-2", existing_count=0)
    assert path_a == path_b
    plan_a = make_toolpath_id(
        "def-1", "bind-1", "strat-x", "geom-a", existing_count=0)
    plan_b = make_toolpath_id(
        "def-1", "bind-1", "strat-x", "geom-a", existing_count=0)
    assert plan_a == plan_b
    assert plan_a.startswith("tp-")


def test_strategy_fingerprint_ignores_label():
    a = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="alpha")
    b = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="beta")
    assert strategy_fingerprint(a) == strategy_fingerprint(b)


def test_strategy_fingerprint_changes_with_computational_fields():
    base = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0)
    assert strategy_fingerprint(base) != strategy_fingerprint(
        replace(base, stepdown_mm=2.0))
    assert strategy_fingerprint(base) != strategy_fingerprint(
        replace(base, travel_height_mm=6.0))
    assert strategy_fingerprint(base) != strategy_fingerprint(
        replace(base, stepover_mm=1.5))
    assert strategy_fingerprint(base) != strategy_fingerprint(
        replace(base, peck_depth_mm=2.0))
    assert strategy_fingerprint(base) != strategy_fingerprint(
        replace(base, retract_height_mm=1.0))


def _upstream(**overrides):
    base = {
        "geometry_ids": ("geom-a",),
        "geometry_digest": "geo-v1",
        "definition_digest": "def-v1",
        "binding_id": "bind-1",
        "tool_diameter_mm": 6.35,
        "tool_flutes": 2,
        "material_id": "hardwood",
        "material_chipload_mm": (0.04, 0.10),
        "recommendation_digest": "rec-v1",
        "strategy_fingerprint": "strat-x",
        "planned_feed_mm_min": 800.0,
    }
    base.update(overrides)
    return upstream_fingerprint(**base)


def test_upstream_fingerprint_is_stable_for_same_inputs():
    assert _upstream() == _upstream()


def test_upstream_fingerprint_reacts_to_computational_changes():
    fp = _upstream()
    assert fp != _upstream(geometry_digest="geo-v2")
    assert fp != _upstream(definition_digest="def-v2")
    assert fp != _upstream(binding_id="bind-2")
    assert fp != _upstream(tool_diameter_mm=3.175)
    assert fp != _upstream(tool_flutes=4)
    assert fp != _upstream(material_id="mdf")
    assert fp != _upstream(material_chipload_mm=(0.05, 0.13))
    assert fp != _upstream(recommendation_digest="rec-v2")
    assert fp != _upstream(strategy_fingerprint="strat-y")
    assert fp != _upstream(planned_feed_mm_min=900.0)
    assert fp != _upstream(geometry_ids=("geom-b",))


def test_upstream_fingerprint_includes_planned_feed_none_distinctly():
    with_feed = _upstream(planned_feed_mm_min=800.0)
    without = _upstream(planned_feed_mm_min=None)
    assert with_feed != without
