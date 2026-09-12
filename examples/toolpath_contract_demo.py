"""Example: construct, persist, and preview a controller-neutral toolpath.

Walks hand-assembled motions — travel, plunge, linear cut, arc cut, retract —
through serialize / reload / preview. This is a contract demonstration.
No contour, pocket, or drill planner runs, and no G-code is emitted.

Run directly::

    python examples/toolpath_contract_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath import (
    MotionKind,
    ToolpathStatus,
    ToolpathStrategy,
    make_arc_motion,
    make_linear_motion,
    make_operation_path,
    make_toolpath_plan,
    toolpath_from_json,
    toolpath_status,
    toolpath_to_json,
    toolpath_to_preview,
)


def main() -> None:
    travel_z = 5.0
    cut_z = -3.0
    feed = 800.0
    geometry_ids = ("geom-a",)
    strategy = ToolpathStrategy(
        travel_height_mm=travel_z, stepdown_mm=3.0, label="demo pass")

    motions = (
        make_linear_motion(
            MotionKind.TRAVEL,
            Point(0, 0, travel_z), Point(10, 0, travel_z),
            index=0, geometry_ids=geometry_ids,
        ),
        make_linear_motion(
            MotionKind.PLUNGE,
            Point(10, 0, travel_z), Point(10, 0, cut_z),
            index=1, planned_feed_mm_min=300.0, geometry_ids=geometry_ids,
        ),
        make_linear_motion(
            MotionKind.CUT,
            Point(10, 0, cut_z), Point(30, 0, cut_z),
            index=2, planned_feed_mm_min=feed, geometry_ids=geometry_ids,
        ),
        make_arc_motion(
            Point(30, 0, cut_z), Point(30, 20, cut_z), Point(30, 10, cut_z),
            False, index=3, planned_feed_mm_min=feed, geometry_ids=geometry_ids,
        ),
        make_linear_motion(
            MotionKind.RETRACT,
            Point(30, 20, cut_z), Point(30, 20, travel_z),
            index=4, geometry_ids=geometry_ids,
        ),
    )
    plan = make_toolpath_plan(
        operation_definition_id="def-1",
        geometry_ids=geometry_ids,
        binding_id="bind-1",
        strategy=strategy,
        paths=(make_operation_path(motions, existing_count=0, depth_mm=3.0),),
        geometry_digest="geo-demo",
        definition_digest="def-demo",
        recommendation_id="rec-1",
        planned_feed_mm_min=feed,
        tool_diameter_mm=6.35,
        tool_flutes=2,
        material_id="hardwood",
        material_chipload_mm=(0.04, 0.10),
    )

    text = toolpath_to_json(plan)
    restored = toolpath_from_json(text)
    segs = toolpath_to_preview(restored)
    kinds = [motion.kind.value for motion in restored.paths[0].motions]
    preview_types = [seg.type for seg in segs]

    print("version:", restored.version)
    print("id:", restored.id)
    print("kinds:", " → ".join(kinds))
    print("status:", toolpath_status(
        restored, restored.upstream_fingerprint).value)
    print("preview types:", " → ".join(preview_types))
    print("source_command empty:", all(seg.source_command == "" for seg in segs))
    print("json bytes:", len(text.encode("utf-8")))
    assert restored == plan
    assert toolpath_status(
        restored, restored.upstream_fingerprint) is ToolpathStatus.CURRENT
    assert "G0" not in text and "source_command" not in text


if __name__ == "__main__":
    main()
