"""Structural validation of stored feed recommendations (CS-014)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cam_creation_studio.feeds_speeds.calculator import FeedRecommendation
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import (
    define_contour,
    define_pocket,
)
from cam_creation_studio.operations.errors import RecommendationError
from cam_creation_studio.operations.models import OperationFeedRecommendation
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_V2,
    OPERATION_PLAN_V3,
    OperationPlan,
    build_operation_plan,
    validate_operation_plan,
)
from cam_creation_studio.operations.recommendations import recommend_feeds_speeds
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _workspace_with(*kinds: OperationKind):
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    for kind in kinds:
        workspace = assign_operation(
            workspace, kind.value, kind, "sel-1", id=f"op-{kind.value}")
    return workspace


def _recommended_plan():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    return recommend_feeds_speeds(plan, "d1", "genericCncRouter", 12000, id="r1")


def _payload() -> FeedRecommendation:
    return FeedRecommendation(
        rpm=12000.0, feed_rate=1200.0, chipload=0.05, surface_speed=1.0)


def test_v2_plan_cannot_carry_recommendations():
    plan = _recommended_plan()
    illegal = replace(plan, version=OPERATION_PLAN_V2)
    with pytest.raises(RecommendationError, match="cannot carry recommendations"):
        validate_operation_plan(illegal)


def test_duplicate_recommendation_ids_are_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    bound = bind_operation(
        bind_operation(
            build_operation_plan(workspace, (contour, pocket)),
            "d1", "endmill_1_4", "hardwood", id="b1"),
        "d2", "endmill_1_8", "mdf", id="b2")
    first = recommend_feeds_speeds(bound, "d1", "genericCncRouter", 12000, id="r1")
    second = recommend_feeds_speeds(first, "d2", "genericCncRouter", 10000, id="r2")
    cloned = replace(second.recommendations[1], id="r1", definition_id="d2")
    illegal = replace(
        second,
        version=OPERATION_PLAN_V3,
        recommendations=(second.recommendations[0], cloned),
    )
    with pytest.raises(RecommendationError, match="duplicate recommendation ID"):
        validate_operation_plan(illegal)


def test_one_recommendation_per_definition():
    plan = _recommended_plan()
    extra = replace(plan.recommendations[0], id="r2")
    illegal = replace(
        plan, recommendations=plan.recommendations + (extra,))
    with pytest.raises(RecommendationError, match="already has a feed recommendation"):
        validate_operation_plan(illegal)


def test_missing_definition_reference_is_rejected():
    plan = _recommended_plan()
    dangling = replace(plan.recommendations[0], definition_id="missing")
    illegal = replace(plan, recommendations=(dangling,))
    with pytest.raises(RecommendationError, match="unknown definition ID"):
        validate_operation_plan(illegal)


def test_binding_owned_by_another_definition_is_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    bound = bind_operation(
        bind_operation(
            build_operation_plan(workspace, (contour, pocket)),
            "d1", "endmill_1_4", "hardwood", id="b1"),
        "d2", "endmill_1_8", "mdf", id="b2")
    plan = recommend_feeds_speeds(bound, "d1", "genericCncRouter", 12000, id="r1")
    stolen = replace(plan.recommendations[0], binding_id="b2")
    illegal = replace(plan, recommendations=(stolen,))
    with pytest.raises(RecommendationError, match="belongs to definition"):
        validate_operation_plan(illegal)


def test_unknown_machine_on_stored_recommendation_is_rejected():
    plan = _recommended_plan()
    broken = replace(plan.recommendations[0], machine_profile_id="missing")
    illegal = replace(plan, recommendations=(broken,))
    with pytest.raises(RecommendationError, match="unknown machine"):
        validate_operation_plan(illegal)


def test_stale_fingerprint_is_still_structurally_valid():
    plan = _recommended_plan()
    stale = replace(plan.recommendations[0], input_fingerprint="outdated")
    validate_operation_plan(replace(plan, recommendations=(stale,)))


def test_unknown_recommendation_type_is_rejected():
    plan = _recommended_plan()
    illegal = OperationPlan(
        version=OPERATION_PLAN_V3,
        workspace=plan.workspace,
        definitions=plan.definitions,
        bindings=plan.bindings,
        recommendations=("nope",),  # type: ignore[arg-type]
    )
    with pytest.raises(RecommendationError, match="unknown recommendation type"):
        validate_operation_plan(illegal)


def test_payload_must_be_canonical_feed_recommendation():
    wrapper = OperationFeedRecommendation(
        id="r1", definition_id="d1", binding_id="b1",
        machine_profile_id="genericCncRouter", spindle_rpm=12000,
        input_fingerprint="fp", recommendation=_payload())
    assert isinstance(wrapper.recommendation, FeedRecommendation)
