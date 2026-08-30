"""Operation-plan v2 bindings persist; v1 documents remain readable."""

from __future__ import annotations

import json

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import define_contour, define_pocket
from cam_creation_studio.operations.errors import BindingError, OperationDefinitionError
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_V1,
    OPERATION_PLAN_V2,
    OPERATION_PLAN_VERSION,
    OperationPlan,
    build_operation_plan,
)
from cam_creation_studio.operations.serialization import (
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


def _workspace():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    workspace = assign_operation(
        workspace, "pocket", OperationKind.POCKET, "sel-1", id="op-pocket")
    return workspace


def _bound_plan():
    workspace = _workspace()
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    plan = build_operation_plan(workspace, (contour, pocket))
    return bind_operation(
        plan, "d1", "endmill_1_4", "hardwood", id="b1")


def test_v2_round_trip_preserves_binding_order_and_ids():
    current = _bound_plan()
    plan = OperationPlan(
        version=OPERATION_PLAN_V2,
        workspace=current.workspace,
        definitions=current.definitions,
        bindings=current.bindings,
    )
    restored = operation_plan_from_dict(operation_plan_to_dict(plan))
    assert restored.version == OPERATION_PLAN_V2
    assert restored.bindings == plan.bindings
    assert "recommendations" not in operation_plan_to_dict(plan)
    assert restored.bindings[0].id == "b1"
    assert restored.bindings[0].definition_id == "d1"
    assert restored.bindings[0].tool_id == "endmill_1_4"
    assert restored.bindings[0].material_id == "hardwood"


def test_v2_json_is_deterministic():
    current = _bound_plan()
    plan = OperationPlan(
        version=OPERATION_PLAN_V2,
        workspace=current.workspace,
        definitions=current.definitions,
        bindings=current.bindings,
    )
    first = operation_plan_to_json(plan)
    second = operation_plan_to_json(plan)
    assert first == second
    payload = json.loads(first)
    assert payload["version"] == OPERATION_PLAN_V2
    assert "recommendations" not in payload
    assert payload["bindings"][0]["tool_id"] == "endmill_1_4"
    assert "timestamp" not in payload
    assert operation_plan_from_json(first) == plan


def test_v1_document_loads_with_empty_bindings():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    v1 = OperationPlan(
        version=OPERATION_PLAN_V1,
        workspace=workspace,
        definitions=(definition,),
    )
    document = operation_plan_to_dict(v1)
    assert document["version"] == OPERATION_PLAN_V1
    assert "bindings" not in document
    restored = operation_plan_from_dict(document)
    assert restored.version == OPERATION_PLAN_V1
    assert restored.bindings == ()
    assert restored.definitions[0].id == "d1"


def test_loading_v1_does_not_rewrite_as_v2():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    document = operation_plan_to_dict(OperationPlan(
        version=OPERATION_PLAN_V1,
        workspace=workspace,
        definitions=(definition,),
    ))
    restored = operation_plan_from_dict(document)
    rewritten = operation_plan_to_dict(restored)
    assert rewritten["version"] == OPERATION_PLAN_V1
    assert "bindings" not in rewritten


def test_binding_mutation_serializes_as_v2():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    v1 = OperationPlan(
        version=OPERATION_PLAN_V1,
        workspace=workspace,
        definitions=(definition,),
    )
    updated = bind_operation(v1, "d1", "endmill_1_4", "mdf", id="b1")
    payload = operation_plan_to_dict(updated)
    assert payload["version"] == OPERATION_PLAN_V2
    assert payload["bindings"] == [{
        "id": "b1",
        "definition_id": "d1",
        "tool_id": "endmill_1_4",
        "material_id": "mdf",
    }]


def test_unknown_tool_on_deserialize_is_rejected():
    plan = _bound_plan()
    document = operation_plan_to_dict(plan)
    document["bindings"][0]["tool_id"] = "missing-tool"
    with pytest.raises(BindingError, match="unknown tool"):
        operation_plan_from_dict(document)


def test_unknown_material_on_deserialize_is_rejected():
    plan = _bound_plan()
    document = operation_plan_to_dict(plan)
    document["bindings"][0]["material_id"] = "missing-material"
    with pytest.raises(BindingError, match="unknown material"):
        operation_plan_from_dict(document)


def test_new_plans_write_current_version_even_when_unbound():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    payload = operation_plan_to_dict(plan)
    assert payload["version"] == OPERATION_PLAN_VERSION
    assert payload["bindings"] == []
    assert payload["recommendations"] == []


def test_unknown_plan_version_still_fails_closed():
    document = operation_plan_to_dict(_bound_plan())
    document["version"] = "camstudio_operation_plan_v9"
    with pytest.raises(OperationDefinitionError, match="unknown operation-plan version"):
        operation_plan_from_dict(document)
