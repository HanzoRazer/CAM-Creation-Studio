"""Operation-plan summaries are deterministic planning counts (CS-012)."""

from __future__ import annotations

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.builder import (
    define_contour,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.summary import summarize_operation_plan
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def test_summary_counts_definitions_allowances_and_depths():
    line = Line2D(start=Point(0, 0), end=Point(4, 0))
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
        define_contour(
            workspace, "op-contour", 6.0, id="d1", stock_allowance_mm=0.5),
        define_pocket(
            workspace, "op-pocket", 4.0, id="d2", wall_allowance_mm=0.0),
        define_reference(workspace, "op-reference", id="d3"),
    ))
    summary = summarize_operation_plan(plan)
    assert summary.definition_count == 3
    assert summary.counts_by_type == {
        "contour": 1,
        "pocket": 1,
        "drill": 0,
        "engrave": 0,
        "slot": 0,
        "reference": 1,
    }
    assert summary.referenced_selection_count == 1
    assert summary.declared_depth_count == 2
    assert summary.allowance_count == 2
    assert summary.definitions_without_tool_count == 3
    assert not hasattr(summary, "timestamp")
    assert not hasattr(summary, "recommended_feed")


def test_empty_plan_has_zero_counts():
    line = Line2D(start=Point(0, 0), end=Point(4, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    summary = summarize_operation_plan(build_operation_plan(workspace))
    assert summary.definition_count == 0
    assert summary.declared_depth_count == 0
    assert summary.allowance_count == 0
    assert summary.definitions_without_tool_count == 0
    assert summary.referenced_selection_count == 0
