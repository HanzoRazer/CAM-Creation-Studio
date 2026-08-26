"""Example: bind a canonical tool and material to an operation definition.

Walks GeometryCollection → workspace → selection → OperationIntent →
ContourDefinition → OperationBinding, then round-trips the operation plan.

This is planning context only. No feed recommendation, machine profile,
toolpath, or G-code is produced.

Run directly::

    python examples/tool_material_binding_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.feeds_speeds.materials import get_material
from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    Line2D,
)
from cam_creation_studio.operations import (
    ContourRelation,
    CutDirection,
    bind_operation,
    build_operation_plan,
    define_contour,
    operation_plan_from_json,
    operation_plan_to_json,
    resolve_material,
    resolve_tool,
    summarize_bindings,
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
        workspace, "outer contour", OperationKind.CONTOUR, "sel-1", id="op-1")

    definition = define_contour(
        workspace, "op-1", 6.0,
        relation=ContourRelation.OUTSIDE,
        direction=CutDirection.CLIMB,
        stock_allowance_mm=0.5,
        id="def-1",
    )
    plan = build_operation_plan(workspace, (definition,))
    plan = bind_operation(
        plan, "def-1", "endmill_1_4", "hardwood", id="bind-1")

    binding = plan.bindings[0]
    tool = resolve_tool(binding)
    material = resolve_material(binding)
    summary = summarize_bindings(plan)

    print(f"Operation plan {plan.version}")
    print(f"  definitions: {summary.definition_count}  "
          f"bound: {summary.bound_definition_count}  "
          f"unbound: {summary.unbound_definition_count}")
    print(f"  binding {binding.id}: definition={binding.definition_id} "
          f"tool={tool.id} ({tool.label}) "
          f"material={material.id} ({material.label})")
    print(f"  catalog identity: tool is get_tool() "
          f"{tool is get_tool('endmill_1_4')}  "
          f"material is get_material() "
          f"{material is get_material('hardwood')}")
    print("  feeds/speeds: not calculated (CS-014)")
    print("  machine profile: not bound")
    print("  toolpath / G-code: not generated")

    text = operation_plan_to_json(plan, indent=2)
    restored = operation_plan_from_json(text)
    print(f"  json bytes: {len(text.encode())}  "
          f"round-trip equal: {restored == plan}")


if __name__ == "__main__":
    main()
