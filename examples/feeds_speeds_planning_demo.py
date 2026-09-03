"""Example: request an advisory feeds/speeds recommendation.

Walks GeometryCollection → workspace → selection → OperationIntent →
ContourDefinition → OperationBinding → MachineProfile + spindle_rpm →
FeedRecommendation, then round-trips the operation plan and inspects
status.

This is advisory planning context only. No toolpath or G-code is produced.
Final target depth is not treated as depth of cut.

Run directly::

    python examples/feeds_speeds_planning_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.feeds_speeds.calculator import calculate_feeds
from cam_creation_studio.feeds_speeds.machines import get_machine
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
    recommend_feeds_speeds,
    recommendation_status,
    resolve_material,
    resolve_tool,
    summarize_feed_recommendations,
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
    plan = recommend_feeds_speeds(
        plan, "def-1", "genericCncRouter", 12000.12345, id="rec-1")

    wrapper = plan.recommendations[0]
    tool = resolve_tool(plan.bindings[0])
    material = resolve_material(plan.bindings[0])
    machine = get_machine(wrapper.machine_profile_id)
    summary = summarize_feed_recommendations(plan)
    direct = calculate_feeds(
        tool_diameter_mm=tool.diameter_mm,
        flutes=tool.flutes,
        spindle_rpm=wrapper.spindle_rpm,
        material=material.id,
        max_rpm=machine.max_rpm,
    )

    print(f"Operation plan {plan.version}")
    print(f"  machining: {summary.machining_definition_count}  "
          f"bound: {summary.bound_definition_count}  "
          f"recommendations: {summary.recommendation_count}  "
          f"current: {summary.current_count}")
    print(f"  requested spindle_rpm: {wrapper.spindle_rpm}  "
          f"calculator rpm: {wrapper.recommendation.rpm}")
    print(f"  feed_rate: {wrapper.recommendation.feed_rate} mm/min  "
          f"direct calculator equal: {wrapper.recommendation == direct}")
    print(f"  MRR/power: {wrapper.recommendation.material_removal_rate} "
          f"(DOC/WOC not supplied)")
    print(f"  status: {recommendation_status(plan, 'def-1').value}")
    print("  toolpath / G-code: not generated")
    print("  machine-ready / safe / approved: not claimed")

    text = operation_plan_to_json(plan, indent=2)
    restored = operation_plan_from_json(text)
    print(f"  json bytes: {len(text.encode())}  "
          f"round-trip equal: {restored == plan}")


if __name__ == "__main__":
    main()
