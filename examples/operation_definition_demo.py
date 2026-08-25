"""Example: record a manufacturing operation definition on workspace intent.

Builds a geometry workspace, attaches a CS-011 contour intent, then records
a CS-012 ContourDefinition with geometry-relative planning parameters.
The operation plan round-trips through JSON.

This is manufacturing planning only. No tool, feeds/speeds, toolpath, or
G-code is produced.

Run directly::

    python examples/operation_definition_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    Line2D,
)
from cam_creation_studio.operations import (
    ContourRelation,
    CutDirection,
    build_operation_plan,
    define_contour,
    operation_plan_from_json,
    operation_plan_to_json,
    summarize_operation_plan,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace import (
    OperationKind,
    assign_operation,
    build_workspace,
    create_selection,
)


def main() -> None:
    collection = GeometryCollection(entities=[
        Line2D(start=Point(0, 0), end=Point(40, 0), layer="cut"),
        Line2D(start=Point(40, 0), end=Point(40, 40), layer="cut"),
        Line2D(start=Point(40, 40), end=Point(0, 40), layer="cut"),
        Line2D(start=Point(0, 40), end=Point(0, 0), layer="cut"),
        Circle2D(center=Point(20, 20), radius=4, layer="holes"),
    ])
    workspace = build_workspace(collection)
    profile_ids = [ref.id for ref in workspace.geometry_refs[:4]]
    workspace = create_selection(workspace, "profile", profile_ids, id="sel-1")
    workspace = assign_operation(
        workspace, "outer contour", OperationKind.CONTOUR, "sel-1",
        id="op-1")

    definition = define_contour(
        workspace, "op-1", 6.0,
        relation=ContourRelation.OUTSIDE,
        direction=CutDirection.CLIMB,
        stock_allowance_mm=0.5,
        id="def-1",
    )
    plan = build_operation_plan(workspace, (definition,))
    summary = summarize_operation_plan(plan)

    print(f"Operation plan {plan.version}")
    print(f"  definitions: {summary.definition_count}  "
          f"depths: {summary.declared_depth_count}  "
          f"allowances: {summary.allowance_count}")
    print(f"  types: {summary.counts_by_type}")
    print(f"  contour {definition.id}: depth={definition.target_depth_mm} mm "
          f"relation={definition.relation.value} "
          f"direction={definition.direction.value} "
          f"stock={definition.stock_allowance_mm} mm")
    print("  tools: not assigned (CS-013)")
    print("  feeds/speeds: not assigned (CS-014)")
    print("  toolpath / G-code: not generated")

    text = operation_plan_to_json(plan, indent=2)
    restored = operation_plan_from_json(text)
    print(f"  json bytes: {len(text.encode())}  "
          f"round-trip equal: {restored == plan}")


if __name__ == "__main__":
    main()
