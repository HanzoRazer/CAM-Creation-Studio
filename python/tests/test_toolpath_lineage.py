"""Lineage: geometry, definition, binding, and recommendation identity (CS-016)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cam_creation_studio.feeds_speeds.materials import get_material
from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation, replace_binding
from cam_creation_studio.operations.builder import define_contour, define_reference
from cam_creation_studio.operations.plan import build_operation_plan, replace_definition
from cam_creation_studio.operations.recommendations import recommend_feeds_speeds
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import (
    build_toolpath_plan,
    make_linear_motion,
    make_operation_path,
)
from cam_creation_studio.toolpath.enums import MotionKind, ToolpathStatus
from cam_creation_studio.toolpath.errors import ToolpathError
from cam_creation_studio.toolpath.fingerprint import (
    definition_digest,
    geometry_digest_for_ids,
    recommendation_digest,
    strategy_fingerprint,
    upstream_fingerprint,
)
from cam_creation_studio.toolpath.models import ToolpathStrategy
from cam_creation_studio.toolpath.status import toolpath_status
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _contour_plan(*, end_x: float = 40.0):
    line = Line2D(start=Point(0, 0), end=Point(end_x, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "contour", OperationKind.CONTOUR, "sel-1", id="op-contour")
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    return bind_operation(plan, "d1", "endmill_1_4", "hardwood", id="b1")


def _paths(operation_plan):
    entity_id = operation_plan.workspace.selections[0].entity_ids[0]
    return (make_operation_path(
        (make_linear_motion(
            MotionKind.CUT, Point(0, 0, 0), Point(10, 0, 0),
            index=0, planned_feed_mm_min=800.0, geometry_ids=(entity_id,)),),
        existing_count=0,
    ),)


def test_build_toolpath_plan_reads_lineage_from_operation_plan():
    operation_plan = recommend_feeds_speeds(
        _contour_plan(), "d1", "genericCncRouter", 12000, id="r1")
    strategy = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0)
    toolpath = build_toolpath_plan(
        operation_plan, "d1", strategy, _paths(operation_plan),
        planned_feed_mm_min=800.0)
    assert toolpath.operation_definition_id == "d1"
    assert toolpath.binding_id == "b1"
    assert toolpath.recommendation_id == "r1"
    assert toolpath.geometry_ids == operation_plan.workspace.selections[0].entity_ids
    assert toolpath_status(
        toolpath, toolpath.upstream_fingerprint) is ToolpathStatus.CURRENT


def _catalog():
    tool = get_tool("endmill_1_4")
    material = get_material("hardwood")
    return {
        "tool_diameter_mm": tool.diameter_mm,
        "tool_flutes": tool.flutes,
        "material_id": material.id,
        "material_chipload_mm": material.chipload_mm,
    }


def test_geometry_coordinate_change_stales_without_changing_ids():
    operation_plan = _contour_plan(end_x=40.0)
    strategy = ToolpathStrategy(travel_height_mm=5.0)
    toolpath = build_toolpath_plan(
        operation_plan, "d1", strategy, _paths(operation_plan),
        planned_feed_mm_min=800.0)
    moved = _contour_plan(end_x=41.0)
    geometry_ids = moved.workspace.selections[0].entity_ids
    current = upstream_fingerprint(
        geometry_ids=geometry_ids,
        geometry_digest=geometry_digest_for_ids(moved.workspace, geometry_ids),
        definition_digest=definition_digest(moved.definitions[0]),
        binding_id="b1",
        recommendation_digest=None,
        strategy_fingerprint=strategy_fingerprint(strategy),
        planned_feed_mm_min=800.0,
        **_catalog(),
    )
    assert toolpath.geometry_ids == geometry_ids
    assert toolpath_status(toolpath, current) is ToolpathStatus.STALE


def test_definition_depth_change_stales():
    operation_plan = _contour_plan()
    strategy = ToolpathStrategy(travel_height_mm=5.0)
    toolpath = build_toolpath_plan(
        operation_plan, "d1", strategy, _paths(operation_plan),
        planned_feed_mm_min=800.0)
    deeper = replace(operation_plan.definitions[0], target_depth_mm=8.0)
    updated = replace_definition(operation_plan, "d1", deeper)
    geometry_ids = updated.workspace.selections[0].entity_ids
    current = upstream_fingerprint(
        geometry_ids=geometry_ids,
        geometry_digest=geometry_digest_for_ids(updated.workspace, geometry_ids),
        definition_digest=definition_digest(updated.definitions[0]),
        binding_id="b1",
        recommendation_digest=None,
        strategy_fingerprint=strategy_fingerprint(strategy),
        planned_feed_mm_min=800.0,
        **_catalog(),
    )
    assert toolpath_status(toolpath, current) is ToolpathStatus.STALE


def test_binding_replacement_stales_via_catalog_fields():
    operation_plan = _contour_plan()
    strategy = ToolpathStrategy(travel_height_mm=5.0)
    toolpath = build_toolpath_plan(
        operation_plan, "d1", strategy, _paths(operation_plan),
        planned_feed_mm_min=800.0)
    swapped = replace_binding(operation_plan, "b1", "endmill_1_8", "hardwood")
    rebuilt = build_toolpath_plan(
        swapped, "d1", strategy, _paths(swapped), planned_feed_mm_min=800.0)
    assert rebuilt.binding_id == "b1"
    assert toolpath_status(
        toolpath, rebuilt.upstream_fingerprint) is ToolpathStatus.STALE


def test_recommendation_notes_do_not_enter_digest():
    operation_plan = recommend_feeds_speeds(
        _contour_plan(), "d1", "genericCncRouter", 12000, id="r1")
    stored = operation_plan.recommendations[0]
    noisier = replace(
        stored.recommendation,
        notes=["operator reminder"],
        warnings=["advisory wording"],
    )
    relabeled = replace(stored, recommendation=noisier)
    assert recommendation_digest(stored) == recommendation_digest(relabeled)


def test_reference_definition_cannot_build_a_plan():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "ref", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "note", OperationKind.REFERENCE, "sel-1", id="op-ref")
    definition = define_reference(workspace, "op-ref", id="d-ref")
    operation_plan = build_operation_plan(workspace, (definition,))
    with pytest.raises(ToolpathError, match="REFERENCE"):
        build_toolpath_plan(
            operation_plan, "d-ref",
            ToolpathStrategy(travel_height_mm=5.0),
            _paths(operation_plan))
