"""Operation-plan JSON is deterministic and fails closed on unknown vocabulary."""

from __future__ import annotations

import json

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_engrave,
    define_pocket,
    define_reference,
    define_slot,
)
from cam_creation_studio.operations.enums import (
    ContourRelation,
    CutDirection,
    SlotRelation,
)
from cam_creation_studio.operations.errors import OperationDefinitionError
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_VERSION,
    build_operation_plan,
)
from cam_creation_studio.operations.serialization import (
    operation_definition_from_dict,
    operation_definition_to_dict,
    operation_plan_from_dict,
    operation_plan_from_json,
    operation_plan_to_dict,
    operation_plan_to_json,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection
from cam_creation_studio.workspace.serialization import workspace_to_dict


def _populated():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    kinds = (
        OperationKind.CONTOUR, OperationKind.POCKET, OperationKind.DRILL,
        OperationKind.ENGRAVE, OperationKind.SLOT, OperationKind.REFERENCE,
    )
    for kind in kinds:
        workspace = assign_operation(
            workspace, kind.value, kind, "sel-1", id=f"op-{kind.value}")
    definitions = (
        define_contour(
            workspace, "op-contour", 6.0, id="d-contour",
            relation=ContourRelation.OUTSIDE,
            direction=CutDirection.CLIMB, stock_allowance_mm=0.4),
        define_pocket(
            workspace, "op-pocket", 4.0, id="d-pocket",
            direction=CutDirection.CONVENTIONAL,
            wall_allowance_mm=0.2, floor_allowance_mm=0.0),
        define_drill(
            workspace, "op-drill", 12.0, id="d-drill",
            retract_height_mm=0.0, peck_depth_mm=3.0),
        define_engrave(workspace, "op-engrave", 0.2, id="d-engrave"),
        define_slot(
            workspace, "op-slot", 5.0, id="d-slot",
            slot_width_mm=6.35, direction=CutDirection.UNSPECIFIED),
        define_reference(workspace, "op-reference", id="d-reference"),
    )
    return build_operation_plan(workspace, definitions)


def test_each_definition_type_round_trips():
    plan = _populated()
    for definition in plan.definitions:
        restored = operation_definition_from_dict(
            operation_definition_to_dict(definition))
        assert restored == definition
        assert type(restored) is type(definition)


def test_plan_round_trip_preserves_enums_and_dimensions():
    plan = _populated()
    restored = operation_plan_from_dict(operation_plan_to_dict(plan))
    assert restored.version == plan.version
    assert restored.workspace == plan.workspace
    assert restored.definitions == plan.definitions
    contour = restored.definitions[0]
    assert contour.relation is ContourRelation.OUTSIDE
    assert contour.direction is CutDirection.CLIMB
    assert contour.stock_allowance_mm == 0.4
    slot = restored.definitions[4]
    assert slot.relation is SlotRelation.ON_PATH
    assert slot.slot_width_mm == 6.35
    assert restored.definitions[5].id == "d-reference"


def test_json_is_deterministic_and_has_no_timestamp():
    plan = _populated()
    first = operation_plan_to_json(plan)
    second = operation_plan_to_json(plan)
    assert first == second
    payload = json.loads(first)
    assert payload["version"] == OPERATION_PLAN_VERSION
    assert "timestamp" not in payload
    assert "created_at" not in payload
    assert payload["definitions"][0]["definition_type"] == "contour"
    restored = operation_plan_from_json(first)
    assert restored == plan


def test_values_remain_millimetres():
    plan = _populated()
    payload = operation_plan_to_dict(plan)
    assert payload["definitions"][0]["target_depth_mm"] == 6.0
    assert "target_depth_in" not in payload["definitions"][0]
    assert "z" not in payload["definitions"][0]


def test_workspace_document_is_not_an_operation_plan():
    plan = _populated()
    with pytest.raises(OperationDefinitionError, match="not an operation plan"):
        operation_plan_from_dict(workspace_to_dict(plan.workspace))


def test_unknown_plan_version_is_rejected():
    document = operation_plan_to_dict(_populated())
    document["version"] = "camstudio_operation_plan_v9"
    with pytest.raises(OperationDefinitionError, match="unknown operation-plan version"):
        operation_plan_from_dict(document)


def test_unknown_definition_type_is_rejected():
    with pytest.raises(OperationDefinitionError, match="unknown definition type"):
        operation_definition_from_dict({
            "definition_type": "chamfer",
            "id": "d1",
            "intent_id": "op-contour",
            "target_depth_mm": 1.0,
        })


def test_unknown_contour_relation_is_rejected():
    payload = operation_definition_to_dict(_populated().definitions[0])
    payload["relation"] = "left"
    with pytest.raises(OperationDefinitionError, match="unknown contour relation"):
        operation_definition_from_dict(payload)


def test_unknown_cut_direction_is_rejected():
    payload = operation_definition_to_dict(_populated().definitions[0])
    payload["direction"] = "both"
    with pytest.raises(OperationDefinitionError, match="unknown cut direction"):
        operation_definition_from_dict(payload)


def test_unknown_slot_relation_is_rejected():
    payload = operation_definition_to_dict(_populated().definitions[4])
    payload["relation"] = "centered"
    with pytest.raises(OperationDefinitionError, match="unknown slot relation"):
        operation_definition_from_dict(payload)


def test_malformed_json_is_rejected():
    with pytest.raises(OperationDefinitionError, match="malformed operation-plan JSON"):
        operation_plan_from_json("{")


def test_non_object_document_is_rejected():
    with pytest.raises(OperationDefinitionError, match="must be an object"):
        operation_plan_from_dict([])


def test_cs011_workspaces_remain_valid_when_embedded():
    plan = _populated()
    document = operation_plan_to_dict(plan)
    assert document["workspace"]["version"] == "camstudio_geometry_workspace_v1"
    restored = operation_plan_from_dict(document)
    assert restored.workspace.operations[0].kind is OperationKind.CONTOUR
