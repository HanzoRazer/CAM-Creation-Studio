"""Operation intent is a category on a selection, not a machining plan (CS-011)."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.ids import make_workspace_object_id
from cam_creation_studio.workspace.models import OperationIntent, OperationKind
from cam_creation_studio.workspace.operations import (
    assign_operation,
    remove_operation,
    replace_operation,
)
from cam_creation_studio.workspace.selections import create_selection


_FORBIDDEN_FIELDS = (
    "tool",
    "tool_id",
    "feed",
    "feed_rate",
    "rpm",
    "spindle_speed",
    "depth",
    "stepdown",
    "stepover",
    "inside",
    "outside",
    "climb",
    "conventional",
    "gcode",
    "machine",
    "postprocessor",
)


def _selected():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    return create_selection(workspace, "profile", [entity_id], id="sel-1")


def test_operation_intent_has_no_machining_fields():
    names = {field.name for field in dataclasses.fields(OperationIntent)}
    assert names == {"id", "name", "kind", "selection_id"}
    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in names


def test_assign_operation_signature_has_no_machining_parameters():
    parameters = set(inspect.signature(assign_operation).parameters)
    assert parameters == {"workspace", "name", "kind", "selection_id", "id"}
    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in parameters


def test_drill_on_a_line_is_structurally_valid():
    workspace = _selected()
    updated = assign_operation(
        workspace, "center punch", OperationKind.DRILL, "sel-1")
    assert updated.operations[0].kind is OperationKind.DRILL
    assert updated.operations[0].selection_id == "sel-1"


def test_kind_may_be_the_enum_value_string():
    workspace = _selected()
    updated = assign_operation(workspace, "trace", "contour", "sel-1")
    assert updated.operations[0].kind is OperationKind.CONTOUR


def test_unknown_kind_is_rejected():
    workspace = _selected()
    with pytest.raises(WorkspaceError, match="unknown operation kind"):
        assign_operation(workspace, "bad", "plunge", "sel-1")


def test_same_selection_may_hold_multiple_intents():
    workspace = _selected()
    first = assign_operation(workspace, "outer", OperationKind.CONTOUR, "sel-1")
    second = assign_operation(first, "label", OperationKind.ENGRAVE, "sel-1")
    assert [op.kind for op in second.operations] == [
        OperationKind.CONTOUR, OperationKind.ENGRAVE]
    assert {op.selection_id for op in second.operations} == {"sel-1"}


def test_generated_id_uses_creation_context():
    workspace = _selected()
    first = assign_operation(workspace, "outer", OperationKind.CONTOUR, "sel-1")
    later = assign_operation(first, "outer", OperationKind.CONTOUR, "sel-1")
    assert first.operations[0].id == make_workspace_object_id(
        "operation", "outer", "sel-1", existing_count=0)
    assert first.operations[0].id != later.operations[1].id


def test_missing_selection_is_rejected():
    workspace = _selected()
    with pytest.raises(WorkspaceError, match="missing selection"):
        assign_operation(workspace, "outer", OperationKind.CONTOUR, "sel-missing")


def test_replace_and_remove_operation():
    workspace = _selected()
    created = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-1")
    replaced = replace_operation(
        created, "op-1", "inner", OperationKind.POCKET, "sel-1")
    assert replaced.operations[0].id == "op-1"
    assert replaced.operations[0].kind is OperationKind.POCKET
    assert replaced.operations[0].name == "inner"
    removed = remove_operation(replaced, "op-1")
    assert removed.operations == ()


def test_remove_unknown_operation_raises():
    workspace = _selected()
    with pytest.raises(WorkspaceError, match="unknown operation ID"):
        remove_operation(workspace, "op-missing")
