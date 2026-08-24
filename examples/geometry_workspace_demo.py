"""Example: load geometry into a planning workspace.

Builds a workspace from imported (or constructed) geometry, inspects it,
records a selection, a group, and a non-executable operation intent, then
round-trips the document through JSON.

This is planning state only. No toolpath, feeds/speeds, or G-code is produced.

Run directly::

    python examples/geometry_workspace_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.diagnostics import GeometryDiagnostic
from cam_creation_studio.geometry.importer import DxfImportError, EzdxfNotInstalled
from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    ImportMetadata,
    Line2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace import (
    OperationKind,
    assign_operation,
    build_workspace,
    create_group,
    create_selection,
    inspect_entity,
    inspect_workspace,
    summarize,
    workspace_from_json,
    workspace_to_json,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "python" / "tests" / "fixtures" / "unsupported_entity.dxf"
)


def _load_collection() -> GeometryCollection:
    """Prefer a real DXF fixture; fall back to an equivalent in-memory set."""
    try:
        from cam_creation_studio.geometry import import_dxf
        return import_dxf(str(FIXTURE))
    except (EzdxfNotInstalled, DxfImportError, OSError) as exc:
        print(f"DXF import unavailable ({exc}); using constructed geometry.")
        return GeometryCollection(
            entities=[
                Line2D(start=Point(0, 0), end=Point(40, 0), layer="cut"),
                Line2D(start=Point(40, 0), end=Point(40, 40), layer="cut"),
                Line2D(start=Point(40, 40), end=Point(0, 40), layer="cut"),
                Line2D(start=Point(0, 40), end=Point(0, 0), layer="cut"),
                Circle2D(center=Point(20, 20), radius=4, layer="holes"),
            ],
            metadata=ImportMetadata(
                source_path="constructed", source_units="mm", unit_scale=1.0,
                entity_count=5, raw_entity_count=6, unsupported_entity_count=1,
            ),
            diagnostics=[
                GeometryDiagnostic(
                    DiagnosticSeverity.WARNING, diag.UNSUPPORTED_ENTITY, "TEXT",
                    entity_type="TEXT", handle="T1"),
            ],
        )


def main() -> None:
    collection = _load_collection()
    workspace = build_workspace(collection)
    overview = inspect_workspace(workspace)
    summary = summarize(workspace)

    print(f"Workspace {overview.version}")
    print(f"  entities: {overview.entity_count}  "
          f"import losses: {overview.import_loss_count}  "
          f"has_lossy_import: {overview.has_lossy_import}")
    print(f"  kinds: {summary.counts_by_kind}")

    for ref in workspace.geometry_refs:
        view = inspect_entity(workspace, ref.id)
        print(f"  {view.id}: {view.kind} layer={view.layer!r} "
              f"handle={view.source_handle!r} loss={view.has_loss}")

    entity_ids = [ref.id for ref in workspace.geometry_refs]
    workspace = create_selection(workspace, "profile", entity_ids[:4])
    workspace = create_group(
        workspace, "body", entity_ids, description="imported outline")
    workspace = assign_operation(
        workspace, "outer contour", OperationKind.CONTOUR,
        workspace.selections[0].id)

    print(f"  selections: {len(workspace.selections)}  "
          f"groups: {len(workspace.groups)}  "
          f"operations: {len(workspace.operations)}")
    print(f"  operation kinds: {summarize(workspace).counts_by_operation_kind}")

    text = workspace_to_json(workspace, indent=2)
    restored = workspace_from_json(text)
    print(f"  json bytes: {len(text.encode())}  "
          f"round-trip equal: {restored == workspace}")


if __name__ == "__main__":
    main()
