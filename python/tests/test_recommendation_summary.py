"""Feed recommendation summary counts, with no readiness semantics (CS-014)."""

from __future__ import annotations

import dataclasses

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation, replace_binding
from cam_creation_studio.operations.builder import (
    define_contour,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.recommendations import recommend_feeds_speeds
from cam_creation_studio.operations.summary import (
    FeedRecommendationSummary,
    summarize_feed_recommendations,
    summarize_operation_plan,
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
    workspace = assign_operation(
        workspace, "note", OperationKind.REFERENCE, "sel-1", id="op-reference")
    return workspace


def _plan():
    workspace = _workspace()
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    reference = define_reference(workspace, "op-reference", id="d3")
    return build_operation_plan(workspace, (contour, pocket, reference))


def test_summary_counts_missing_before_any_recommendation():
    plan = bind_operation(_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    summary = summarize_feed_recommendations(plan)
    assert summary.machining_definition_count == 2
    assert summary.bound_definition_count == 1
    assert summary.recommendation_count == 0
    assert summary.current_count == 0
    assert summary.stale_count == 0
    assert summary.missing_count == 2
    assert summary.warning_count == 0


def test_summary_counts_current_stale_missing_and_warnings():
    plan = bind_operation(_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    plan = recommend_feeds_speeds(plan, "d1", "desktop3018", 18000, id="r1")
    plan = replace_binding(plan, "b1", "endmill_1_8", "hardwood")
    summary = summarize_feed_recommendations(plan)
    assert summary.recommendation_count == 1
    assert summary.current_count == 0
    assert summary.stale_count == 1
    assert summary.missing_count == 1
    assert summary.warning_count >= 1


def test_summary_has_no_readiness_or_safety_fields():
    names = {field.name for field in dataclasses.fields(FeedRecommendationSummary)}
    assert names == {
        "machining_definition_count",
        "bound_definition_count",
        "recommendation_count",
        "current_count",
        "stale_count",
        "missing_count",
        "warning_count",
    }
    for forbidden in (
        "readiness", "ready_count", "safety_score", "machine_ready",
        "approved", "quality_score",
    ):
        assert forbidden not in names


def test_summary_does_not_call_the_calculator(monkeypatch):
    plan = recommend_feeds_speeds(
        bind_operation(_plan(), "d1", "endmill_1_4", "hardwood", id="b1"),
        "d1", "genericCncRouter", 12000, id="r1")

    def boom(*_args, **_kwargs):
        raise AssertionError("calculator must not run during summary")

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", boom)
    summary = summarize_feed_recommendations(plan)
    assert summary.current_count == 1


def test_operation_plan_summary_still_does_not_claim_tool_readiness():
    plan = recommend_feeds_speeds(
        bind_operation(_plan(), "d1", "endmill_1_4", "hardwood", id="b1"),
        "d1", "genericCncRouter", 12000, id="r1")
    summary = summarize_operation_plan(plan)
    assert summary.definitions_without_tool_count == 3
    names = {field.name for field in dataclasses.fields(summary)}
    assert "machine_ready" not in names
    assert "ready_count" not in names
