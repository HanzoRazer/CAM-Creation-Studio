"""Structural validation of tool/material bindings (CS-013)."""

from __future__ import annotations

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import (
    define_contour,
    define_reference,
)
from cam_creation_studio.operations.errors import BindingError
from cam_creation_studio.operations.models import OperationBinding
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_V1,
    OperationPlan,
    build_operation_plan,
    validate_operation_plan,
)
from cam_creation_studio.operations.validation import validate_operation_bindings
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _contour_and_reference():
    line = Line2D(start=Point(0, 0), end=Point(8, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    workspace = assign_operation(
        workspace, "keep", OperationKind.REFERENCE, "sel-1", id="op-reference")
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    reference = define_reference(workspace, "op-reference", id="d-ref")
    return build_operation_plan(workspace, (contour, reference))


def test_duplicate_binding_ids_are_rejected():
    plan = _contour_and_reference()
    first = OperationBinding(
        id="dup", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    second = OperationBinding(
        id="dup", definition_id="d1",
        tool_id="endmill_1_8", material_id="mdf")
    with pytest.raises(BindingError, match="duplicate binding ID"):
        validate_operation_bindings(plan.definitions, (first, second))


def test_duplicate_definition_ownership_is_rejected():
    plan = _contour_and_reference()
    first = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    second = OperationBinding(
        id="b2", definition_id="d1",
        tool_id="endmill_1_8", material_id="mdf")
    with pytest.raises(BindingError, match="already has a binding"):
        validate_operation_bindings(plan.definitions, (first, second))


def test_dangling_definition_reference_is_rejected():
    plan = _contour_and_reference()
    binding = OperationBinding(
        id="b1", definition_id="missing",
        tool_id="endmill_1_4", material_id="hardwood")
    with pytest.raises(BindingError, match="unknown definition ID"):
        validate_operation_bindings(plan.definitions, (binding,))


def test_v1_plan_cannot_carry_bindings():
    plan = _contour_and_reference()
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    invalid = OperationPlan(
        version=OPERATION_PLAN_V1,
        workspace=plan.workspace,
        definitions=plan.definitions,
        bindings=(binding,),
    )
    with pytest.raises(BindingError, match="v1 cannot carry bindings"):
        validate_operation_plan(invalid)


def test_empty_binding_ids_are_rejected():
    plan = _contour_and_reference()
    with pytest.raises(BindingError, match="binding ID"):
        validate_operation_bindings(plan.definitions, (
            OperationBinding(
                id="", definition_id="d1",
                tool_id="endmill_1_4", material_id="hardwood"),
        ))


def test_unbound_plan_validates():
    plan = _contour_and_reference()
    assert validate_operation_plan(plan) is None
    assert plan.bindings == ()


def test_bound_plan_validates_without_judging_suitability():
    plan = bind_operation(
        _contour_and_reference(), "d1", "laser_diode", "mild_steel", id="b1")
    assert validate_operation_plan(plan) is None
