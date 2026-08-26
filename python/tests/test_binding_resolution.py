"""Canonical Tool and Material resolution for operation bindings (CS-013)."""

from __future__ import annotations

import pytest

from cam_creation_studio.feeds_speeds.materials import Material, get_material
from cam_creation_studio.feeds_speeds.tools import Tool, get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.builder import define_contour, define_reference
from cam_creation_studio.operations.errors import BindingError
from cam_creation_studio.operations.models import OperationBinding
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.resolution import (
    require_bindable_definition,
    require_definition,
    resolve_definition,
    resolve_material,
    resolve_tool,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _plan_with_contour():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    return build_operation_plan(workspace, (definition,))


def test_resolve_tool_returns_canonical_catalog_object():
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    tool = resolve_tool(binding)
    assert type(tool) is Tool
    assert tool is get_tool("endmill_1_4")
    assert tool.id == "endmill_1_4"
    assert tool.diameter_mm == pytest.approx(6.35, abs=1e-9)


def test_resolve_material_returns_canonical_catalog_object():
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="mdf")
    material = resolve_material(binding)
    assert type(material) is Material
    assert material is get_material("mdf")
    assert material.id == "mdf"
    assert material.chipload_mid == pytest.approx(
        sum(material.chipload_mm) / 2)


def test_unknown_tool_is_a_binding_error():
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="missing-tool", material_id="hardwood")
    with pytest.raises(BindingError, match="unknown tool"):
        resolve_tool(binding)


def test_unknown_material_is_a_binding_error():
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="missing-material")
    with pytest.raises(BindingError, match="unknown material"):
        resolve_material(binding)


def test_resolve_definition_uses_plan_identity():
    plan = _plan_with_contour()
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    definition = resolve_definition(plan, binding)
    assert definition is plan.definitions[0]
    assert require_definition(plan, "d1") is definition


def test_unknown_definition_is_a_binding_error():
    plan = _plan_with_contour()
    binding = OperationBinding(
        id="b1", definition_id="missing",
        tool_id="endmill_1_4", material_id="hardwood")
    with pytest.raises(BindingError, match="unknown definition ID"):
        resolve_definition(plan, binding)


def test_reference_definition_is_not_bindable():
    line = Line2D(start=Point(0, 0), end=Point(4, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "keep", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "keep", OperationKind.REFERENCE, "sel-1", id="op-reference")
    definition = define_reference(workspace, "op-reference", id="d-ref")
    with pytest.raises(BindingError, match="REFERENCE"):
        require_bindable_definition(definition)
