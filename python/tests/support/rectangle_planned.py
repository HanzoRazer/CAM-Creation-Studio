"""Build the synthetic rectangular-planner fixture.

Values here are software-test numbers. They are not approved cutting data.
The stored feed recommendation is intentionally not selected.
"""

from __future__ import annotations

import json
from pathlib import Path

from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import define_contour
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.recommendations import recommend_feeds_speeds
from cam_creation_studio.operations.serialization import operation_plan_to_json
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.traceability.compatibility import (
    ADMISSION_CONTRACT,
    FIXTURE_PRODUCER,
    FIXTURE_VERSION,
    GEOMETRY_CONTRACT,
    PROPOSAL_CONTRACT,
    REQUEST_VERSION,
    SUBJECT_CONTRACT,
    SUPPORTED_FRAME,
    SUPPORTED_OPERATION,
    SUPPORTED_PROFILE,
    SUPPORTED_UNITS,
    VALIDATION_CONTRACT,
)
from cam_creation_studio.traceability.encoding import sha256_bytes
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection

PACKAGE_ID = "pkg-synthetic-rectangle-planned-1"
SUBJECT_ID = "specimen-synthetic-rectangle-1"
GEOMETRY_ID = "geom-rectangle-planned-1"
REVISION = "rev-1"
PROPOSAL_ID = "prop-rectangle-planned-1"
VALIDATION_ID = "val-rectangle-planned-1"
ADMISSION_ID = "adm-rectangle-planned-1"
REQUEST_ID = "req-rectangle-planned-1"
FRAME_NAME = "stock-fixed rectangular coupon"
CENTER = (20.0, 15.0, 60.0, 35.0)
REMOVAL = (10.0, 5.0, 70.0, 45.0)
MAX_DEPTH_MM = 3.0
TOLERANCE_MM = 0.05
DEPTH_LEVELS = (1.0, 2.0)
TARGET_DEPTH_MM = 2.0
TRAVEL_MM = 5.0
CLEARANCE_MM = 5.0
STEPDOWN_MM = 1.0
CUT_FEED = 800
PLUNGE_FEED = 300
TOOL_ID = "endmill_1_4"
MATERIAL_ID = "hardwood"
STOCK_ID = "stock-coupon-rect-80x50x10"

TOOL = get_tool(TOOL_ID)
TOOL_DIAMETER_MM = TOOL.diameter_mm


def golden_lines() -> list[Line2D]:
    """Four Z0 sides in an order that is not the traversal order."""
    x0, y0, x1, y1 = CENTER
    return [
        Line2D(Point(x1, y1, 0), Point(x0, y1, 0)),
        Line2D(Point(x0, y0, 0), Point(x1, y0, 0)),
        Line2D(Point(x0, y1, 0), Point(x0, y0, 0)),
        Line2D(Point(x1, y0, 0), Point(x1, y1, 0)),
    ]


def make_operation_plan(
    lines: list | None = None,
    *,
    relation: str = "on",
    direction: str = "unspecified",
    allowance: float | None = 0.0,
    target_depth_mm: float = TARGET_DEPTH_MM,
    tool_id: str = TOOL_ID,
    material_id: str = MATERIAL_ID,
    with_recommendation: bool = True,
    spindle_rpm: float = 12000,
):
    """One contour, one binding, and an unselected recommendation by default."""
    collection = GeometryCollection(entities=list(lines if lines is not None else golden_lines()))
    workspace = build_workspace(collection)
    entity_ids = tuple(ref.id for ref in workspace.geometry_refs)
    workspace = create_selection(workspace, "rectangle", entity_ids)
    selection_id = workspace.selections[0].id
    workspace = assign_operation(
        workspace, "contour", OperationKind.CONTOUR, selection_id)
    intent_id = workspace.operations[0].id
    definition = define_contour(
        workspace,
        intent_id,
        target_depth_mm,
        relation=relation,
        direction=direction,
        stock_allowance_mm=allowance,
    )
    plan = build_operation_plan(workspace, (definition,))
    plan = bind_operation(plan, definition.id, tool_id, material_id)
    if with_recommendation:
        plan = recommend_feeds_speeds(
            plan, definition.id, "genericCncRouter", spindle_rpm)
    return plan


def write_planned_package(root: Path) -> Path:
    """Write one immutable package. Software-test values only."""
    if root.exists():
        for child in root.iterdir():
            if child.is_file() and not child.is_symlink():
                child.unlink()
    root.mkdir(parents=True, exist_ok=True)
    plan = make_operation_plan()
    plan_text = operation_plan_to_json(plan, indent=2, sort_keys=True) + "\n"
    (root / "operation_plan.json").write_text(plan_text, encoding="utf-8")
    plan_sha = sha256_bytes((root / "operation_plan.json").read_bytes())
    _write_upstream(root)
    request_sha = sha256_bytes((root / "request.json").read_bytes())
    planner_input = {
        "contract_version": "creation-studio.rectangular-planner-input/1",
        "definition_id": plan.definitions[0].id,
        "operation_plan": {
            "package_ref": "operation_plan.json",
            "sha256": plan_sha,
        },
        "planned_cut_feed_mm_min": CUT_FEED,
        "planned_plunge_feed_mm_min": PLUNGE_FEED,
        "recommendation_id": None,
        "request_sha256": request_sha,
    }
    _write(root / "planner-inputs.json", planner_input)
    (root / "NOTES.txt").write_text(
        "\n".join([
            "Software-test values only. EXPERIMENTAL — NOT FOR MACHINING.",
            f"Tool {TOOL_ID} resolves to diameter {TOOL_DIAMETER_MM} mm, kind endmill.",
            "Request tooling.kind is flat_end_mill. Material is hardwood.",
            "Centerline (20, 15) to (60, 35). Depths are 1 mm and 2 mm.",
            "Cut feed 800 mm/min and plunge feed 300 mm/min are explicit selections.",
            "The stored feed recommendation is not selected.",
            "",
        ]),
        encoding="utf-8",
    )
    return root


def _write_upstream(root: Path) -> None:
    subject = {
        "artifact_id": "subject-rectangle-planned-1",
        "contract_id": SUBJECT_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "kind": "synthetic_rectangular_coupon",
        "subject_id": SUBJECT_ID,
    }
    geometry = {
        "artifact_id": GEOMETRY_ID,
        "contract_id": GEOMETRY_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "coordinate_frame_id": SUPPORTED_FRAME,
        "geometry_id": GEOMETRY_ID,
        "kind": "rectangle",
        "revision": REVISION,
        "units": SUPPORTED_UNITS,
        "x_max_mm": CENTER[2],
        "x_min_mm": CENTER[0],
        "y_max_mm": CENTER[3],
        "y_min_mm": CENTER[1],
    }
    proposal = {
        "artifact_id": PROPOSAL_ID,
        "contract_id": PROPOSAL_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "coordinate_frame_id": SUPPORTED_FRAME,
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": REVISION,
        "operation_type": SUPPORTED_OPERATION,
        "package_id": PACKAGE_ID,
        "proposal_id": PROPOSAL_ID,
        "subject_id": SUBJECT_ID,
        "units": SUPPORTED_UNITS,
    }
    _write(root / "subject.json", subject)
    _write(root / "geometry.json", geometry)
    _write(root / "proposal.json", proposal)
    proposal_sha = sha256_bytes((root / "proposal.json").read_bytes())
    validation = {
        "artifact_id": VALIDATION_ID,
        "contract_id": VALIDATION_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": REVISION,
        "package_id": PACKAGE_ID,
        "proposal_digest": proposal_sha,
        "proposal_id": PROPOSAL_ID,
        "result": "recorded_for_fixture",
        "subject_id": SUBJECT_ID,
        "validation_id": VALIDATION_ID,
    }
    _write(root / "validation.json", validation)
    validation_sha = sha256_bytes((root / "validation.json").read_bytes())
    admission = {
        "artifact_id": ADMISSION_ID,
        "contract_id": ADMISSION_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "current_state": "not_established",
        "disposition": "admitted_for_human_review",
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": REVISION,
        "package_id": PACKAGE_ID,
        "producer_id": FIXTURE_PRODUCER,
        "proposal_digest": proposal_sha,
        "proposal_id": PROPOSAL_ID,
        "subject_id": SUBJECT_ID,
        "validation_digest": validation_sha,
        "validation_id": VALIDATION_ID,
    }
    _write(root / "admission.json", admission)
    hashes = {
        "proposal": proposal_sha,
        "validation": validation_sha,
        "admission": sha256_bytes((root / "admission.json").read_bytes()),
        "geometry": sha256_bytes((root / "geometry.json").read_bytes()),
        "subject": sha256_bytes((root / "subject.json").read_bytes()),
    }
    ids = {
        "proposal": PROPOSAL_ID,
        "validation": VALIDATION_ID,
        "admission": ADMISSION_ID,
        "geometry": GEOMETRY_ID,
        "subject": "subject-rectangle-planned-1",
    }
    contracts = {
        "proposal": PROPOSAL_CONTRACT,
        "validation": VALIDATION_CONTRACT,
        "admission": ADMISSION_CONTRACT,
        "geometry": GEOMETRY_CONTRACT,
        "subject": SUBJECT_CONTRACT,
    }
    files = {
        "proposal": "proposal.json",
        "validation": "validation.json",
        "admission": "admission.json",
        "geometry": "geometry.json",
        "subject": "subject.json",
    }
    request = {
        "contract_version": REQUEST_VERSION,
        "coordinate_frame": {"id": SUPPORTED_FRAME, "name": FRAME_NAME},
        "geometry": {"id": GEOMETRY_ID, "revision": REVISION},
        "machine_profile": {"id": SUPPORTED_PROFILE},
        "operation": {
            "centerline": {
                "x_max_mm": CENTER[2],
                "x_min_mm": CENTER[0],
                "y_max_mm": CENTER[3],
                "y_min_mm": CENTER[1],
            },
            "type": SUPPORTED_OPERATION,
        },
        "package_id": PACKAGE_ID,
        "positional_tolerance_mm": TOLERANCE_MM,
        "removal_region": {
            "max_depth_mm": MAX_DEPTH_MM,
            "x_max_mm": REMOVAL[2],
            "x_min_mm": REMOVAL[0],
            "y_max_mm": REMOVAL[3],
            "y_min_mm": REMOVAL[1],
        },
        "request_id": REQUEST_ID,
        "stock": {
            "id": STOCK_ID,
            "material_id": MATERIAL_ID,
            "x_mm": 80.0,
            "y_mm": 50.0,
            "z_mm": 10.0,
        },
        "strategy": {
            "clearance_mm": CLEARANCE_MM,
            "depth_levels_mm": list(DEPTH_LEVELS),
            "id": "strat-rectangle-planned-1",
            "stepdown_mm": STEPDOWN_MM,
            "stock_allowance_mm": 0.0,
            "travel_height_mm": TRAVEL_MM,
        },
        "subject": {"id": SUBJECT_ID},
        "tooling": {
            "diameter_mm": TOOL_DIAMETER_MM,
            "id": TOOL_ID,
            "kind": "flat_end_mill",
            "orientation": "fixed",
        },
        "units": SUPPORTED_UNITS,
        "upstream_artifacts": [
            {
                "artifact_id": ids[role],
                "contract_id": contracts[role],
                "contract_version": FIXTURE_VERSION,
                "package_ref": files[role],
                "role": role,
                "sha256": hashes[role],
            }
            for role in (
                "proposal", "validation", "admission", "geometry", "subject")
        ],
        "workflow_origin": "imported",
    }
    _write(root / "request.json", request)


def _write(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
