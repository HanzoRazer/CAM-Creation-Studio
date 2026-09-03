"""Resolve recommendation inputs without invoking the calculator (CS-014)."""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.feeds_speeds.machines import get_machine
from cam_creation_studio.feeds_speeds.materials import get_material
from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import (
    define_contour,
    define_reference,
)
from cam_creation_studio.operations.errors import RecommendationError
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.resolution import (
    require_calculator_tool,
    require_recommendable_definition,
    resolve_machine_profile,
    resolve_recommendation_inputs,
    validate_spindle_rpm,
)
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


def _bound_contour_plan():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    return bind_operation(plan, "d1", "endmill_1_4", "hardwood", id="b1")


def test_resolve_machine_profile_returns_canonical_catalog_object():
    machine = resolve_machine_profile("genericCncRouter")
    assert machine is get_machine("genericCncRouter")
    assert machine.max_rpm == 18000.0


def test_unknown_machine_is_a_recommendation_error():
    with pytest.raises(RecommendationError, match="unknown machine 'missing'"):
        resolve_machine_profile("missing")


def test_validate_spindle_rpm_requires_finite_positive():
    assert validate_spindle_rpm(12000.12345) == 12000.12345
    for bad in (0, -1, math.nan, math.inf, True, "12000", None):
        with pytest.raises(RecommendationError, match="spindle_rpm"):
            validate_spindle_rpm(bad)


def test_resolve_recommendation_inputs_reuses_canonical_catalogs():
    plan = _bound_contour_plan()
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000.12345)
    assert inputs.definition.id == "d1"
    assert inputs.binding.id == "b1"
    assert inputs.tool is get_tool("endmill_1_4")
    assert inputs.material is get_material("hardwood")
    assert inputs.machine is get_machine("genericCncRouter")
    assert inputs.spindle_rpm == 12000.12345


def test_unbound_definition_cannot_resolve_recommendation_inputs():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    with pytest.raises(RecommendationError, match="has no tool/material binding"):
        resolve_recommendation_inputs(plan, "d1", "genericCncRouter", 12000)


def test_unknown_definition_is_a_recommendation_error():
    plan = _bound_contour_plan()
    with pytest.raises(RecommendationError, match="unknown definition ID"):
        resolve_recommendation_inputs(plan, "missing", "genericCncRouter", 12000)


def test_reference_definition_cannot_receive_a_recommendation():
    workspace = _workspace_with(OperationKind.REFERENCE)
    definition = define_reference(workspace, "op-reference", id="d1")
    plan = build_operation_plan(workspace, (definition,))
    with pytest.raises(RecommendationError, match="REFERENCE definition"):
        require_recommendable_definition(definition)
    with pytest.raises(RecommendationError, match="REFERENCE definition"):
        resolve_recommendation_inputs(plan, "d1", "genericCncRouter", 12000)


def test_laser_and_knife_tools_are_not_calculator_inputs():
    for tool_id in ("laser_diode", "drag_knife"):
        tool = get_tool(tool_id)
        with pytest.raises(
            RecommendationError,
            match=f"tool '{tool_id}' does not provide flute-count input",
        ):
            require_calculator_tool(tool)


def test_bound_laser_cannot_resolve_recommendation_inputs():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "laser_diode", "hardwood", id="b1")
    with pytest.raises(
        RecommendationError,
        match="tool 'laser_diode' does not provide flute-count input",
    ):
        resolve_recommendation_inputs(plan, "d1", "genericCncRouter", 12000)


def test_machine_without_max_rpm_is_valid_recommendation_context():
    plan = _bound_contour_plan()
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericLaser", 12000)
    assert inputs.machine is get_machine("genericLaser")
    assert inputs.machine.max_rpm is None
