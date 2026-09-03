"""Operation-plan v3 recommendations persist; v1/v2 remain readable."""

from __future__ import annotations

import json

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import define_contour
from cam_creation_studio.operations.errors import (
    OperationDefinitionError,
    RecommendationError,
)
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_V1,
    OPERATION_PLAN_V2,
    OPERATION_PLAN_V3,
    OperationPlan,
    build_operation_plan,
)
from cam_creation_studio.operations.recommendations import recommend_feeds_speeds
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
    return workspace


def _recommended_plan():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    return recommend_feeds_speeds(
        plan, "d1", "genericCncRouter", 12000.12345, id="r1")


def test_v3_round_trip_preserves_recommendation_and_warnings():
    plan = _recommended_plan()
    restored = operation_plan_from_dict(operation_plan_to_dict(plan))
    assert restored.version == OPERATION_PLAN_V3
    assert restored.recommendations == plan.recommendations
    wrapper = restored.recommendations[0]
    assert wrapper.id == "r1"
    assert wrapper.spindle_rpm == 12000.12345
    assert wrapper.machine_profile_id == "genericCncRouter"
    assert wrapper.input_fingerprint == plan.recommendations[0].input_fingerprint
    assert wrapper.recommendation == plan.recommendations[0].recommendation
    assert [item.code for item in wrapper.recommendation.diagnostics]


def test_v3_json_is_deterministic():
    plan = _recommended_plan()
    first = operation_plan_to_json(plan)
    second = operation_plan_to_json(plan)
    assert first == second
    payload = json.loads(first)
    assert payload["version"] == OPERATION_PLAN_V3
    assert payload["recommendations"][0]["spindle_rpm"] == 12000.12345
    assert "timestamp" not in payload
    assert operation_plan_from_json(first) == plan


def test_read_does_not_call_the_calculator(monkeypatch):
    plan = _recommended_plan()
    document = operation_plan_to_dict(plan)

    def boom(*_args, **_kwargs):
        raise AssertionError("calculator must not run during read")

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", boom)
    monkeypatch.setattr(
        "cam_creation_studio.feeds_speeds.calculator.calculate_feeds", boom)
    restored = operation_plan_from_dict(document)
    assert restored.recommendations[0].recommendation.feed_rate == (
        plan.recommendations[0].recommendation.feed_rate)


def test_v1_document_loads_without_recommendations():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    v1 = OperationPlan(
        version=OPERATION_PLAN_V1,
        workspace=workspace,
        definitions=(definition,),
    )
    document = operation_plan_to_dict(v1)
    assert "bindings" not in document
    assert "recommendations" not in document
    restored = operation_plan_from_dict(document)
    assert restored.version == OPERATION_PLAN_V1
    assert restored.bindings == ()
    assert restored.recommendations == ()
    rewritten = operation_plan_to_dict(restored)
    assert rewritten["version"] == OPERATION_PLAN_V1
    assert "recommendations" not in rewritten


def test_v2_document_loads_without_recommendations():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    bound = bind_operation(
        OperationPlan(
            version=OPERATION_PLAN_V1,
            workspace=workspace,
            definitions=(definition,),
        ),
        "d1", "endmill_1_4", "hardwood", id="b1")
    assert bound.version == OPERATION_PLAN_V2
    document = operation_plan_to_dict(bound)
    assert document["version"] == OPERATION_PLAN_V2
    assert "recommendations" not in document
    restored = operation_plan_from_dict(document)
    assert restored.version == OPERATION_PLAN_V2
    assert restored.bindings[0].id == "b1"
    assert restored.recommendations == ()
    rewritten = operation_plan_to_dict(restored)
    assert rewritten["version"] == OPERATION_PLAN_V2
    assert "recommendations" not in rewritten


def test_recommendation_mutation_upgrades_v2_to_v3():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    v2 = bind_operation(
        OperationPlan(
            version=OPERATION_PLAN_V1,
            workspace=workspace,
            definitions=(definition,),
        ),
        "d1", "endmill_1_4", "hardwood", id="b1")
    updated = recommend_feeds_speeds(v2, "d1", "genericCncRouter", 12000, id="r1")
    payload = operation_plan_to_dict(updated)
    assert payload["version"] == OPERATION_PLAN_V3
    assert payload["recommendations"][0]["id"] == "r1"


def test_v2_document_with_recommendations_key_fails_closed():
    workspace = _workspace()
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    document = operation_plan_to_dict(OperationPlan(
        version=OPERATION_PLAN_V2,
        workspace=workspace,
        definitions=(definition,),
    ))
    document["recommendations"] = [{"id": "r1"}]
    with pytest.raises(RecommendationError, match="cannot carry recommendations"):
        operation_plan_from_dict(document)


def test_unknown_machine_on_deserialize_is_rejected():
    document = operation_plan_to_dict(_recommended_plan())
    document["recommendations"][0]["machine_profile_id"] = "missing-machine"
    with pytest.raises(RecommendationError, match="unknown machine"):
        operation_plan_from_dict(document)


def test_unknown_plan_version_fails_closed():
    document = operation_plan_to_dict(_recommended_plan())
    document["version"] = "camstudio_operation_plan_v9"
    with pytest.raises(OperationDefinitionError, match="unknown operation-plan version"):
        operation_plan_from_dict(document)
