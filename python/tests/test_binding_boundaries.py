"""CS-013 constitutional boundaries: binding is declaration, not calculation."""

from __future__ import annotations

import dataclasses
import inspect

from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import define_contour
from cam_creation_studio.operations.models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationBinding,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
)
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import GeometryWorkspace, OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection

_FORBIDDEN_ON_BINDING = (
    "rpm",
    "feed",
    "feed_rate",
    "chipload",
    "chipload_mm",
    "chipload_mid",
    "surface_speed",
    "stepdown",
    "stepover",
    "power",
    "torque",
    "machine",
    "machine_id",
    "postprocessor",
    "gcode",
    "diameter_mm",
    "flutes",
    "pass_count",
    "entry_strategy",
)

_DEFINITION_CLASSES = (
    ContourDefinition,
    PocketDefinition,
    DrillDefinition,
    EngraveDefinition,
    SlotDefinition,
    ReferenceDefinition,
)


def test_binding_contract_has_no_execution_or_catalog_copy_fields():
    names = {field.name for field in dataclasses.fields(OperationBinding)}
    for forbidden in _FORBIDDEN_ON_BINDING:
        assert forbidden not in names


def test_bind_operation_signature_has_no_execution_parameters():
    parameters = set(inspect.signature(bind_operation).parameters)
    for forbidden in _FORBIDDEN_ON_BINDING:
        assert forbidden not in parameters
    assert parameters == {
        "plan", "definition_id", "tool_id", "material_id", "id",
    }


def test_definitions_still_do_not_carry_tool_or_material():
    for cls in _DEFINITION_CLASSES:
        names = {field.name for field in dataclasses.fields(cls)}
        assert "tool_id" not in names
        assert "material_id" not in names
        assert "tool" not in names
        assert "material" not in names


def test_workspace_does_not_own_bindings():
    names = {field.name for field in dataclasses.fields(GeometryWorkspace)}
    assert "bindings" not in names
    assert "tool_id" not in names


def test_binding_does_not_mutate_the_tool_catalog():
    line = Line2D(start=Point(0, 0), end=Point(4, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-contour")
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace, (definition,))
    before = get_tool("endmill_1_4")
    diameter = before.diameter_mm
    bind_operation(plan, "d1", "endmill_1_4", "hardwood")
    after = get_tool("endmill_1_4")
    assert after is before
    assert after.diameter_mm == diameter
