"""Workspace summaries are deterministic planning counts (CS-011)."""

from __future__ import annotations

from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.diagnostics import GeometryDiagnostic
from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    Line2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.groups import create_group
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection
from cam_creation_studio.workspace.summary import summarize


def test_summary_includes_zero_counts_for_absent_kinds():
    collection = GeometryCollection(
        entities=[
            Line2D(start=Point(0, 0), end=Point(4, 0)),
            Circle2D(center=Point(1, 1), radius=2),
        ],
        diagnostics=[
            GeometryDiagnostic(
                DiagnosticSeverity.WARNING, diag.UNSUPPORTED_ENTITY, "TEXT",
                entity_type="TEXT", handle="T1"),
        ],
    )
    workspace = build_workspace(collection)
    ids = [ref.id for ref in workspace.geometry_refs]
    workspace = create_selection(workspace, "holes", [ids[1]], id="sel-1")
    workspace = create_group(workspace, "all", ids)
    workspace = assign_operation(
        workspace, "drill", OperationKind.DRILL, "sel-1")
    workspace = assign_operation(
        workspace, "keep", OperationKind.REFERENCE, "sel-1")

    summary = summarize(workspace)
    assert summary.entity_count == 2
    assert summary.selection_count == 1
    assert summary.group_count == 1
    assert summary.operation_count == 2
    assert summary.counts_by_kind == {
        "line": 1, "arc": 0, "circle": 1, "polyline": 0, "spline": 0,
    }
    assert summary.counts_by_operation_kind == {
        "contour": 0,
        "pocket": 0,
        "drill": 1,
        "engrave": 0,
        "slot": 0,
        "reference": 1,
    }
    assert summary.import_loss_count == 1
    assert not hasattr(summary, "timestamp")
