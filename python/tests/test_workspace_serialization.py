"""Versioned workspace JSON is deterministic and structurally validated (CS-011)."""

from __future__ import annotations

import json

import pytest

from cam_creation_studio.geometry.models import (
    Circle2D,
    GeometryCollection,
    Line2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.groups import create_group
from cam_creation_studio.workspace.models import WORKSPACE_VERSION, OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection
from cam_creation_studio.workspace.serialization import (
    workspace_from_dict,
    workspace_from_json,
    workspace_to_dict,
    workspace_to_json,
)


def _populated():
    collection = GeometryCollection(entities=[
        Line2D(start=Point(0, 0), end=Point(10, 0)),
        Circle2D(center=Point(2, 2), radius=1),
    ])
    workspace = build_workspace(collection)
    ids = [ref.id for ref in workspace.geometry_refs]
    workspace = create_selection(workspace, "profile", [ids[0]], id="sel-1")
    workspace = create_group(workspace, "body", ids, description="all")
    workspace = assign_operation(
        workspace, "outer", OperationKind.CONTOUR, "sel-1", id="op-1")
    return workspace


def test_round_trip_preserves_workspace_state():
    workspace = _populated()
    restored = workspace_from_dict(workspace_to_dict(workspace))
    assert restored.version == workspace.version
    assert restored.geometry == workspace.geometry
    assert restored.geometry_refs == workspace.geometry_refs
    assert restored.selections == workspace.selections
    assert restored.groups == workspace.groups
    assert restored.operations == workspace.operations


def test_json_is_deterministic_and_has_no_timestamp():
    workspace = _populated()
    first = workspace_to_json(workspace)
    second = workspace_to_json(workspace)
    assert first == second
    payload = json.loads(first)
    assert payload["version"] == WORKSPACE_VERSION
    assert "timestamp" not in payload
    assert "created_at" not in payload
    assert payload["operations"][0]["kind"] == "contour"
    restored = workspace_from_json(first)
    assert restored.operations[0].kind is OperationKind.CONTOUR


def test_geometry_collection_document_is_not_a_workspace():
    collection = GeometryCollection(entities=[
        Line2D(start=Point(0, 0), end=Point(3, 0)),
    ])
    with pytest.raises(WorkspaceError, match="not a workspace document"):
        workspace_from_dict(collection.to_dict())


def test_unknown_version_is_rejected():
    document = workspace_to_dict(_populated())
    document["version"] = "camstudio_geometry_workspace_v9"
    with pytest.raises(WorkspaceError, match="unknown workspace version"):
        workspace_from_dict(document)


def test_unknown_operation_kind_is_rejected():
    document = workspace_to_dict(_populated())
    document["operations"][0]["kind"] = "plunge"
    with pytest.raises(WorkspaceError, match="unknown operation kind"):
        workspace_from_dict(document)


def test_dangling_selection_reference_is_rejected_on_load():
    document = workspace_to_dict(_populated())
    document["operations"][0]["selection_id"] = "sel-missing"
    with pytest.raises(WorkspaceError, match="missing selection"):
        workspace_from_dict(document)


def test_malformed_json_is_rejected():
    with pytest.raises(WorkspaceError, match="malformed workspace JSON"):
        workspace_from_json("{")
