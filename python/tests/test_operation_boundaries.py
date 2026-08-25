"""CS-012 constitutional boundaries: planning only, no execution."""

from __future__ import annotations

import dataclasses
import inspect

from cam_creation_studio.operations import builder as builder_mod
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_engrave,
    define_pocket,
    define_reference,
    define_slot,
)
from cam_creation_studio.operations.models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
)
from cam_creation_studio.workspace.models import GeometryWorkspace

_FORBIDDEN = (
    "tool",
    "tool_id",
    "material",
    "material_id",
    "feed",
    "feed_rate",
    "rpm",
    "chipload",
    "surface_speed",
    "stepdown",
    "stepover",
    "lead_in",
    "lead_out",
    "tabs",
    "ramp",
    "helix",
    "gcode",
    "machine",
    "machine_id",
    "postprocessor",
    "cutter_diameter",
    "tool_number",
    "entry_strategy",
    "pass_count",
)

_DEFINITION_CLASSES = (
    ContourDefinition,
    PocketDefinition,
    DrillDefinition,
    EngraveDefinition,
    SlotDefinition,
    ReferenceDefinition,
)

_BUILDERS = (
    define_contour,
    define_pocket,
    define_drill,
    define_engrave,
    define_slot,
    define_reference,
)


def test_no_definition_contract_exposes_execution_fields():
    for cls in _DEFINITION_CLASSES:
        names = {field.name for field in dataclasses.fields(cls)}
        for forbidden in _FORBIDDEN:
            assert forbidden not in names, f"{cls.__name__}.{forbidden}"


def test_no_builder_accepts_execution_parameters():
    for func in _BUILDERS:
        parameters = set(inspect.signature(func).parameters)
        for forbidden in _FORBIDDEN:
            assert forbidden not in parameters, f"{func.__name__}({forbidden})"


def test_builder_module_has_no_toolpath_helpers():
    names = set(dir(builder_mod))
    for forbidden in (
        "offset", "compensate", "generate_toolpath", "to_gcode",
        "recommend_stepdown", "recommend_stepover", "canned_cycle",
    ):
        assert forbidden not in names


def test_geometry_workspace_does_not_own_definitions():
    names = {field.name for field in dataclasses.fields(GeometryWorkspace)}
    assert "operation_definitions" not in names
    assert "definitions" not in names
    assert "operation_plan" not in names


def test_workspace_models_do_not_import_operations_package():
    import cam_creation_studio.workspace.models as workspace_models

    assert not hasattr(workspace_models, "OperationDefinition")
    source = inspect.getsource(workspace_models)
    assert "cam_creation_studio.operations" not in source
    assert "from ..operations" not in source
