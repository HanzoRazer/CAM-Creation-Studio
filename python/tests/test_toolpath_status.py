"""Staleness of a stored toolpath versus current upstream inputs (CS-016)."""

from __future__ import annotations

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import (
    make_linear_motion,
    make_operation_path,
    make_toolpath_plan,
)
from cam_creation_studio.toolpath.enums import MotionKind, ToolpathStatus
from cam_creation_studio.toolpath.fingerprint import (
    strategy_fingerprint,
    upstream_fingerprint,
)
from cam_creation_studio.toolpath.models import ToolpathStrategy
from cam_creation_studio.toolpath.status import toolpath_status


def _kwargs(**overrides):
    base = {
        "operation_definition_id": "def-1",
        "geometry_ids": ("geom-a",),
        "binding_id": "bind-1",
        "strategy": ToolpathStrategy(
            travel_height_mm=5.0, stepdown_mm=3.0, label="alpha"),
        "paths": (make_operation_path(
            (make_linear_motion(
                MotionKind.CUT, Point(0, 0, 0), Point(10, 0, 0),
                index=0, planned_feed_mm_min=800.0),),
            existing_count=0,
        ),),
        "geometry_digest": "geo-v1",
        "definition_digest": "def-v1",
        "recommendation_digest": "rec-v1",
        "recommendation_id": "rec-1",
        "planned_feed_mm_min": 800.0,
        "tool_diameter_mm": 6.35,
        "tool_flutes": 2,
        "material_id": "hardwood",
        "material_chipload_mm": (0.04, 0.10),
    }
    base.update(overrides)
    return base


def _plan(**overrides):
    return make_toolpath_plan(**_kwargs(**overrides))


def _fingerprint_for(**overrides):
    kwargs = _kwargs(**overrides)
    strategy = kwargs["strategy"]
    return upstream_fingerprint(
        geometry_ids=kwargs["geometry_ids"],
        geometry_digest=kwargs["geometry_digest"],
        definition_digest=kwargs["definition_digest"],
        binding_id=kwargs["binding_id"],
        tool_diameter_mm=kwargs["tool_diameter_mm"],
        tool_flutes=kwargs["tool_flutes"],
        material_id=kwargs["material_id"],
        material_chipload_mm=kwargs["material_chipload_mm"],
        recommendation_digest=kwargs["recommendation_digest"],
        strategy_fingerprint=strategy_fingerprint(strategy),
        planned_feed_mm_min=kwargs["planned_feed_mm_min"],
    )


def test_missing_when_no_plan():
    assert toolpath_status(None, "up-anything") is ToolpathStatus.MISSING


def test_current_when_fingerprint_matches():
    plan = _plan()
    assert toolpath_status(plan, plan.upstream_fingerprint) is ToolpathStatus.CURRENT
    assert toolpath_status(plan, _fingerprint_for()) is ToolpathStatus.CURRENT


def test_geometry_change_is_stale():
    plan = _plan()
    current = _fingerprint_for(geometry_digest="geo-v2")
    assert toolpath_status(plan, current) is ToolpathStatus.STALE


def test_binding_change_is_stale():
    plan = _plan()
    current = _fingerprint_for(binding_id="bind-2")
    assert toolpath_status(plan, current) is ToolpathStatus.STALE


def test_recommendation_change_is_stale():
    plan = _plan()
    current = _fingerprint_for(recommendation_digest="rec-v2")
    assert toolpath_status(plan, current) is ToolpathStatus.STALE


def test_strategy_computational_change_is_stale():
    plan = _plan()
    current = _fingerprint_for(
        strategy=ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=2.0))
    assert toolpath_status(plan, current) is ToolpathStatus.STALE


def test_planned_feed_change_is_stale():
    plan = _plan()
    current = _fingerprint_for(planned_feed_mm_min=650.0)
    assert toolpath_status(plan, current) is ToolpathStatus.STALE


def test_strategy_label_does_not_stale():
    plan = _plan()
    current = _fingerprint_for(
        strategy=ToolpathStrategy(
            travel_height_mm=5.0, stepdown_mm=3.0, label="beta"))
    assert toolpath_status(plan, current) is ToolpathStatus.CURRENT


def test_status_does_not_equal_regeneration():
    plan = _plan()
    stale = _fingerprint_for(geometry_digest="geo-moved")
    assert toolpath_status(plan, stale) is ToolpathStatus.STALE
    assert plan.paths[0].motions[0].end == Point(10, 0, 0)
