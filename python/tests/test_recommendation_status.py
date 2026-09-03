"""Fingerprint and staleness of stored feed recommendations (CS-014)."""

from __future__ import annotations

from dataclasses import replace

from cam_creation_studio.feeds_speeds.machines import get_machine
from cam_creation_studio.feeds_speeds.materials import get_material
from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation, replace_binding
from cam_creation_studio.operations.builder import define_contour
from cam_creation_studio.operations.enums import RecommendationStatus
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.recommendations import (
    feed_input_fingerprint,
    recommend_feeds_speeds,
    recommendation_status,
)
from cam_creation_studio.operations.resolution import (
    RecommendationInputs,
    resolve_recommendation_inputs,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _bound_contour_plan():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "contour", OperationKind.CONTOUR, "sel-1", id="op-contour")
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    return bind_operation(plan, "d1", "endmill_1_4", "hardwood", id="b1")


def test_missing_status_when_no_recommendation():
    plan = _bound_contour_plan()
    assert recommendation_status(plan, "d1") is RecommendationStatus.MISSING


def test_current_status_matches_stored_fingerprint():
    plan = recommend_feeds_speeds(
        _bound_contour_plan(), "d1", "genericCncRouter", 12000, id="r1")
    assert recommendation_status(plan, "d1") is RecommendationStatus.CURRENT


def test_binding_replacement_makes_recommendation_stale():
    plan = recommend_feeds_speeds(
        _bound_contour_plan(), "d1", "genericCncRouter", 12000, id="r1")
    updated = replace_binding(plan, "b1", "endmill_1_8", "hardwood")
    assert updated.recommendations[0].id == "r1"
    assert recommendation_status(updated, "d1") is RecommendationStatus.STALE
    assert recommendation_status(plan, "d1") is RecommendationStatus.CURRENT


def test_contemplated_machine_mismatch_is_stale_and_does_not_mutate():
    plan = recommend_feeds_speeds(
        _bound_contour_plan(), "d1", "genericCncRouter", 12000, id="r1")
    assert recommendation_status(
        plan, "d1", machine_profile_id="desktop3018") is RecommendationStatus.STALE
    assert plan.recommendations[0].machine_profile_id == "genericCncRouter"
    assert recommendation_status(
        plan, "d1", machine_profile_id="genericCncRouter") is RecommendationStatus.CURRENT


def test_status_does_not_call_the_calculator(monkeypatch):
    plan = recommend_feeds_speeds(
        _bound_contour_plan(), "d1", "genericCncRouter", 12000, id="r1")

    def boom(*_args, **_kwargs):
        raise AssertionError("calculator must not run during status")

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", boom)
    monkeypatch.setattr(
        "cam_creation_studio.feeds_speeds.calculator.calculate_feeds", boom)
    assert recommendation_status(plan, "d1") is RecommendationStatus.CURRENT
    assert recommendation_status(
        plan, "d1", machine_profile_id="desktop3018") is RecommendationStatus.STALE


def test_fingerprint_ignores_labels_and_notes():
    plan = _bound_contour_plan()
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000.12345)
    relabeled = RecommendationInputs(
        definition=inputs.definition,
        binding=inputs.binding,
        tool=replace(inputs.tool, label="other", notes="changed"),
        material=replace(inputs.material, label="other", notes="changed"),
        machine=replace(inputs.machine, label="other", notes="changed"),
        spindle_rpm=inputs.spindle_rpm,
    )
    assert feed_input_fingerprint(inputs) == feed_input_fingerprint(relabeled)


def test_fingerprint_changes_when_calculation_inputs_change():
    plan = _bound_contour_plan()
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000.12345)
    base = feed_input_fingerprint(inputs)
    assert feed_input_fingerprint(replace(
        inputs, tool=replace(inputs.tool, diameter_mm=inputs.tool.diameter_mm + 1),
    )) != base
    assert feed_input_fingerprint(replace(
        inputs, tool=replace(inputs.tool, flutes=inputs.tool.flutes + 1),
    )) != base
    assert feed_input_fingerprint(replace(
        inputs, material=replace(inputs.material, chipload_mm=(0.01, 0.02)),
    )) != base
    assert feed_input_fingerprint(replace(
        inputs, machine=replace(inputs.machine, max_rpm=9000.0),
    )) != base
    assert feed_input_fingerprint(replace(inputs, spindle_rpm=8000.0)) != base


def test_requested_spindle_rpm_is_preserved_apart_from_rounded_output():
    plan = recommend_feeds_speeds(
        _bound_contour_plan(), "d1", "genericCncRouter", 12000.12345, id="r1")
    wrapper = plan.recommendations[0]
    assert wrapper.spindle_rpm == 12000.12345
    assert wrapper.recommendation.rpm != 12000.12345
    assert "12000.12345" in wrapper.input_fingerprint
    assert recommendation_status(plan, "d1") is RecommendationStatus.CURRENT


def test_catalog_identity_helpers_used_by_fingerprint():
    assert get_tool("endmill_1_4").diameter_mm > 0
    assert get_material("hardwood").chipload_mm[0] > 0
    assert get_machine("genericCncRouter").max_rpm == 18000.0
