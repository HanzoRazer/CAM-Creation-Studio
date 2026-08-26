"""Binding summaries are deterministic counts, not readiness claims."""

from __future__ import annotations

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import (
    define_contour,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.summary import summarize_bindings
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def test_summary_counts_bound_and_unbound_definitions():
    line = Line2D(start=Point(0, 0), end=Point(6, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    workspace = assign_operation(
        workspace, "pocket", OperationKind.POCKET, "sel-1", id="op-pocket")
    workspace = assign_operation(
        workspace, "keep", OperationKind.REFERENCE, "sel-1", id="op-reference")
    plan = build_operation_plan(workspace, (
        define_contour(workspace, "op-contour", 6.0, id="d1"),
        define_pocket(workspace, "op-pocket", 4.0, id="d2"),
        define_reference(workspace, "op-reference", id="d3"),
    ))
    plan = bind_operation(plan, "d1", "endmill_1_4", "hardwood", id="b1")
    summary = summarize_bindings(plan)
    assert summary.definition_count == 3
    assert summary.bound_definition_count == 1
    assert summary.unbound_definition_count == 2
    assert summary.counts_by_tool_kind["endmill"] == 1
    assert summary.counts_by_tool_kind["ballnose"] == 0
    assert summary.counts_by_material["hardwood"] == 1
    assert summary.counts_by_material["mdf"] == 0
    assert not hasattr(summary, "ready")
    assert not hasattr(summary, "recommended_feed")
    assert not hasattr(summary, "score")


def test_empty_bindings_are_all_unbound():
    line = Line2D(start=Point(0, 0), end=Point(6, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    plan = build_operation_plan(workspace, (
        define_contour(workspace, "op-contour", 6.0, id="d1"),
    ))
    summary = summarize_bindings(plan)
    assert summary.bound_definition_count == 0
    assert summary.unbound_definition_count == 1
    assert summary.counts_by_tool_kind["endmill"] == 0
