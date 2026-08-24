"""Group helpers reject empty groups and preserve caller order (CS-011)."""

from __future__ import annotations

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.groups import (
    create_group,
    remove_group,
    replace_group,
)
from cam_creation_studio.workspace.ids import make_workspace_object_id


def _workspace(count=3):
    entities = [
        Line2D(start=Point(i, 0), end=Point(i + 1, 0)) for i in range(count)
    ]
    return build_workspace(GeometryCollection(entities=entities))


def test_create_group_preserves_caller_order_and_description():
    workspace = _workspace()
    ids = [ref.id for ref in workspace.geometry_refs]
    updated = create_group(
        workspace, "body", [ids[1], ids[0]], description="outline")
    assert updated.groups[0].entity_ids == (ids[1], ids[0])
    assert updated.groups[0].description == "outline"
    assert updated.groups[0].name == "body"


def test_empty_group_is_rejected():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="empty"):
        create_group(workspace, "none", [])


def test_duplicate_member_ids_are_rejected():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    with pytest.raises(WorkspaceError, match="duplicate entity IDs"):
        create_group(workspace, "dup", [entity_id, entity_id])


def test_missing_entity_id_is_rejected():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="missing entity"):
        create_group(workspace, "gone", ["geom-missing"])


def test_generated_id_uses_creation_context():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    first = create_group(workspace, "body", [entity_id])
    later = create_group(first, "body", [entity_id])
    assert first.groups[0].id == make_workspace_object_id(
        "group", "body", entity_id, existing_count=0)
    assert first.groups[0].id != later.groups[1].id


def test_replace_and_remove_group():
    workspace = _workspace()
    ids = [ref.id for ref in workspace.geometry_refs]
    created = create_group(workspace, "body", [ids[0]], description="first")
    group_id = created.groups[0].id
    replaced = replace_group(
        created, group_id, "shell", [ids[1], ids[2]], description="updated")
    assert replaced.groups[0].id == group_id
    assert replaced.groups[0].name == "shell"
    assert replaced.groups[0].entity_ids == (ids[1], ids[2])
    assert replaced.groups[0].description == "updated"
    removed = remove_group(replaced, group_id)
    assert removed.groups == ()


def test_remove_unknown_group_raises():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="unknown group ID"):
        remove_group(workspace, "grp-missing")
