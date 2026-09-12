"""Versioned toolpath JSON is deterministic and fails closed."""

from __future__ import annotations

import json

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
from cam_creation_studio.toolpath.models import TOOLPATH_PLAN_V1, ToolpathStrategy
from cam_creation_studio.toolpath.serialization import (
    toolpath_from_dict,
    toolpath_from_json,
    toolpath_to_dict,
    toolpath_to_json,
)

_FORBIDDEN = (
    "source_command", "G0", "G1", "G2", "G3", "M3", "M5",
    "MoveType", "ToolpathSegment", "ArcMove", "dialect", "controller",
    "postprocessor", "machine_ready", "approved", "burn", "extrude",
)


def _sample_plan():
    h = 5.0
    feed = 800.0
    g = ("geom-a",)
    motions = (
        make_linear_motion(
            MotionKind.TRAVEL, Point(0, 0, h), Point(0, 0, 0), index=0,
            geometry_ids=g),
        make_linear_motion(
            MotionKind.PLUNGE, Point(0, 0, 0), Point(0, 0, -3), index=1,
            planned_feed_mm_min=feed, geometry_ids=g),
        make_linear_motion(
            MotionKind.CUT, Point(0, 0, -3), Point(20, 0, -3), index=2,
            planned_feed_mm_min=feed, geometry_ids=g),
        make_arc_motion(
            Point(20, 0, -3), Point(20, 20, -3), Point(20, 10, -3), False,
            index=3, planned_feed_mm_min=feed, geometry_ids=g),
        make_linear_motion(
            MotionKind.RETRACT, Point(20, 20, -3), Point(20, 20, h), index=4,
            geometry_ids=g),
    )
    return make_toolpath_plan(
        operation_definition_id="def-1",
        geometry_ids=g,
        binding_id="bind-1",
        strategy=ToolpathStrategy(travel_height_mm=h, stepdown_mm=3.0, label="keep"),
        paths=(make_operation_path(motions, existing_count=0, depth_mm=3.0),),
        geometry_digest="geo-v1",
        definition_digest="def-v1",
        recommendation_digest="rec-v1",
        recommendation_id="rec-1",
        planned_feed_mm_min=feed,
        tool_diameter_mm=6.35,
        tool_flutes=2,
        material_id="hardwood",
        material_chipload_mm=(0.04, 0.10),
    )


def test_round_trip_preserves_plan():
    plan = _sample_plan()
    restored = toolpath_from_json(toolpath_to_json(plan))
    assert restored == plan
    assert restored.version == TOOLPATH_PLAN_V1
    assert restored.upstream_fingerprint == plan.upstream_fingerprint


def test_json_is_deterministic():
    plan = _sample_plan()
    first = toolpath_to_json(plan)
    second = toolpath_to_json(toolpath_from_json(first))
    assert first == second
    payload = json.loads(first)
    assert list(payload.keys()) == sorted(payload.keys())


def test_motion_order_is_not_sorted():
    plan = _sample_plan()
    kinds = [m["kind"] for m in toolpath_to_dict(plan)["paths"][0]["motions"]]
    assert kinds == ["travel", "plunge", "cut", "cut", "retract"]
    restored = toolpath_from_dict(toolpath_to_dict(plan))
    assert [m.kind.value for m in restored.paths[0].motions] == kinds


def test_unknown_version_fails_closed():
    payload = toolpath_to_dict(_sample_plan())
    payload["version"] = "camstudio_toolpath_v999"
    with pytest.raises(ToolpathError, match="unknown toolpath-plan version"):
        toolpath_from_dict(payload)


def test_unknown_motion_form_fails_closed():
    payload = toolpath_to_dict(_sample_plan())
    payload["paths"][0]["motions"][0]["form"] = "bezier"
    with pytest.raises(ToolpathError, match="unknown motion form"):
        toolpath_from_dict(payload)


def test_unknown_motion_kind_fails_closed():
    payload = toolpath_to_dict(_sample_plan())
    payload["paths"][0]["motions"][2]["kind"] = "burn"
    with pytest.raises(ToolpathError, match="unknown motion kind"):
        toolpath_from_dict(payload)


def test_malformed_json_is_rejected():
    with pytest.raises(ToolpathError, match="malformed toolpath-plan JSON"):
        toolpath_from_json("{")


def test_non_object_document_is_rejected():
    with pytest.raises(ToolpathError, match="must be an object"):
        toolpath_from_dict([])


def test_serialization_has_no_forbidden_vocabulary():
    text = toolpath_to_json(_sample_plan())
    for token in _FORBIDDEN:
        assert token not in text, token
    assert '"Move"' not in text
    assert "safe_" not in text
    assert "camstudio_toolpath_plan_v1" not in text
    assert '"role"' not in text
    assert "source_fingerprint" not in text
