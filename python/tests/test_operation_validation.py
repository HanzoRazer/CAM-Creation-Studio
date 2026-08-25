"""Structural validation of operation definitions against workspace intent."""

from __future__ import annotations

import pytest

from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    Line2D,
    Polyline2D,
)
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.enums import ContourRelation, CutDirection
from cam_creation_studio.operations.errors import OperationDefinitionError
from cam_creation_studio.operations.models import (
    ContourDefinition,
    DrillDefinition,
    PocketDefinition,
    ReferenceDefinition,
)
from cam_creation_studio.operations.validation import (
    validate_operation_definition,
    validate_operation_definitions,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import (
    assign_operation,
    remove_operation,
)
from cam_creation_studio.workspace.selections import create_selection


def _workspace_with(*kinds: OperationKind, entity=None):
    if entity is None:
        entity = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[entity]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    for kind in kinds:
        workspace = assign_operation(
            workspace, kind.value, kind, "sel-1", id=f"op-{kind.value}")
    return workspace


def test_valid_definition_returns_none():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    assert validate_operation_definition(workspace, definition) is None


def test_contour_on_pocket_intent_is_rejected():
    workspace = _workspace_with(OperationKind.POCKET)
    definition = ContourDefinition(
        id="d1", intent_id="op-pocket", target_depth_mm=6.0)
    with pytest.raises(OperationDefinitionError, match="contour"):
        validate_operation_definition(workspace, definition)


def test_drill_on_drill_intent_is_valid():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = DrillDefinition(
        id="d1", intent_id="op-drill", target_depth_mm=8.0)
    validate_operation_definition(workspace, definition)


def test_missing_intent_is_a_definition_error():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = ContourDefinition(
        id="d1", intent_id="op-missing", target_depth_mm=6.0)
    with pytest.raises(OperationDefinitionError, match="unknown operation intent"):
        validate_operation_definition(workspace, definition)


def test_empty_ids_are_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR)
    with pytest.raises(OperationDefinitionError, match="definition ID"):
        validate_operation_definition(
            workspace,
            ContourDefinition(id="", intent_id="op-contour", target_depth_mm=1.0),
        )
    with pytest.raises(OperationDefinitionError, match="intent_id"):
        validate_operation_definition(
            workspace,
            ContourDefinition(id="d1", intent_id="", target_depth_mm=1.0),
        )


def test_raw_zero_depth_is_rejected_at_validation():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = ContourDefinition(
        id="d1", intent_id="op-contour", target_depth_mm=0.0)
    with pytest.raises(OperationDefinitionError, match="target_depth_mm"):
        validate_operation_definition(workspace, definition)


def test_string_enum_members_are_rejected_until_coerced():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = ContourDefinition(
        id="d1", intent_id="op-contour", target_depth_mm=1.0,
        relation="on",  # type: ignore[arg-type]
    )
    with pytest.raises(OperationDefinitionError, match="relation"):
        validate_operation_definition(workspace, definition)


def test_duplicate_definition_ids_are_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    first = define_contour(workspace, "op-contour", 6.0, id="dup")
    second = define_pocket(workspace, "op-pocket", 4.0, id="dup")
    with pytest.raises(OperationDefinitionError, match="duplicate definition ID"):
        validate_operation_definitions(workspace, (first, second))


def test_one_definition_per_intent():
    workspace = _workspace_with(OperationKind.CONTOUR)
    first = define_contour(workspace, "op-contour", 6.0, id="d1")
    second = define_contour(
        workspace, "op-contour", 3.0, id="d2", existing_count=1)
    with pytest.raises(OperationDefinitionError, match="already has a definition"):
        validate_operation_definitions(workspace, (first, second))


def test_distinct_intents_may_each_have_a_definition():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    definitions = (
        define_contour(workspace, "op-contour", 6.0, id="d1"),
        define_pocket(workspace, "op-pocket", 4.0, id="d2"),
    )
    assert validate_operation_definitions(workspace, definitions) is None


def test_reference_definition_requires_reference_intent():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.REFERENCE)
    with pytest.raises(OperationDefinitionError, match="reference"):
        validate_operation_definition(
            workspace, ReferenceDefinition(id="d1", intent_id="op-contour"))
    validate_operation_definition(
        workspace, ReferenceDefinition(id="d1", intent_id="op-reference"))


def test_removing_a_referenced_intent_is_detected_on_revalidation():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    updated = remove_operation(workspace, "op-contour")
    with pytest.raises(OperationDefinitionError, match="unknown operation intent"):
        validate_operation_definition(updated, definition)


def test_drill_on_a_line_is_structurally_valid():
    workspace = _workspace_with(
        OperationKind.DRILL, entity=Line2D(start=Point(0, 0), end=Point(4, 0)))
    definition = define_drill(workspace, "op-drill", 5.0)
    validate_operation_definition(workspace, definition)


def test_pocket_on_an_open_polyline_is_structurally_valid():
    polyline = Polyline2D(
        vertices=[Point(0, 0), Point(10, 0), Point(10, 8)], closed=False)
    workspace = _workspace_with(OperationKind.POCKET, entity=polyline)
    definition = define_pocket(workspace, "op-pocket", 3.0)
    validate_operation_definition(workspace, definition)


def test_contour_on_a_circle_is_structurally_valid():
    workspace = _workspace_with(
        OperationKind.CONTOUR, entity=Circle2D(center=Point(2, 2), radius=1))
    definition = define_contour(
        workspace, "op-contour", 1.5, relation=ContourRelation.INSIDE,
        direction=CutDirection.CONVENTIONAL)
    validate_operation_definition(workspace, definition)
