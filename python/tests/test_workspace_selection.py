"""Selection helpers preserve caller order and reject invalid members (CS-011)."""

from __future__ import annotations

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.ids import make_workspace_object_id
from cam_creation_studio.workspace.models import OperationIntent, OperationKind
from cam_creation_studio.workspace.refs import workspace_replace
from cam_creation_studio.workspace.selections import (
    create_selection,
    remove_selection,
    replace_selection,
)
from cam_creation_studio.workspace.validation import validate_workspace


def _workspace(count=3):
    entities = [
        Line2D(start=Point(i, 0), end=Point(i + 1, 0)) for i in range(count)
    ]
    return build_workspace(GeometryCollection(entities=entities))


def test_create_selection_preserves_caller_order():
    workspace = _workspace()
    ids = [ref.id for ref in workspace.geometry_refs]
    updated = create_selection(workspace, "outer", [ids[2], ids[0], ids[1]])
    assert updated.selections[0].entity_ids == (ids[2], ids[0], ids[1])
    assert updated.selections[0].name == "outer"
    assert updated.geometry is workspace.geometry


def test_empty_selection_is_rejected():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="empty"):
        create_selection(workspace, "none", [])


def test_duplicate_member_ids_are_rejected_without_dedup():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    with pytest.raises(WorkspaceError, match="duplicate entity IDs"):
        create_selection(workspace, "dup", [entity_id, entity_id])


def test_missing_entity_id_is_rejected():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="missing entity"):
        create_selection(workspace, "gone", ["geom-missing"])


def test_duplicate_names_are_allowed_ids_are_not():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    first = create_selection(workspace, "outer", [entity_id])
    second = create_selection(first, "outer", [entity_id])
    assert second.selections[0].name == second.selections[1].name == "outer"
    assert second.selections[0].id != second.selections[1].id
    with pytest.raises(WorkspaceError, match="duplicate selection ID"):
        create_selection(first, "other", [entity_id], id=first.selections[0].id)


def test_generated_id_is_creation_context_not_content_addressed():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    first = create_selection(workspace, "outer", [entity_id])
    same_content_later = create_selection(first, "outer", [entity_id])
    assert first.selections[0].id != same_content_later.selections[1].id
    expected = make_workspace_object_id(
        "selection", "outer", entity_id, existing_count=0)
    assert first.selections[0].id == expected


def test_equivalent_helper_sequences_produce_equivalent_ids():
    workspace = _workspace()
    ids = [ref.id for ref in workspace.geometry_refs]
    a = create_selection(
        create_selection(workspace, "a", [ids[0]]), "b", [ids[1]])
    b = create_selection(
        create_selection(workspace, "a", [ids[0]]), "b", [ids[1]])
    assert [s.id for s in a.selections] == [s.id for s in b.selections]


def test_explicit_id_is_honored():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    updated = create_selection(workspace, "outer", [entity_id], id="sel-custom")
    assert updated.selections[0].id == "sel-custom"


def test_replace_keeps_id_and_renaming_does_not_mint_a_new_one():
    workspace = _workspace()
    ids = [ref.id for ref in workspace.geometry_refs]
    created = create_selection(workspace, "outer", [ids[0]])
    selection_id = created.selections[0].id
    replaced = replace_selection(created, selection_id, "renamed", [ids[1]])
    assert replaced.selections[0].id == selection_id
    assert replaced.selections[0].name == "renamed"
    assert replaced.selections[0].entity_ids == (ids[1],)


def test_remove_selection_rejects_when_an_operation_references_it():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    selected = create_selection(workspace, "holes", [entity_id], id="sel-holes")
    referenced = workspace_replace(
        selected,
        operations=(
            OperationIntent(
                id="op-1", name="drill", kind=OperationKind.DRILL,
                selection_id="sel-holes"),
        ),
    )
    validate_workspace(referenced)
    with pytest.raises(WorkspaceError, match=r"operations \['op-1'\]"):
        remove_selection(referenced, "sel-holes")
    assert referenced.selections[0].id == "sel-holes"


def test_remove_selection_succeeds_after_dependent_operations_are_removed():
    workspace = _workspace()
    entity_id = workspace.geometry_refs[0].id
    selected = create_selection(workspace, "holes", [entity_id], id="sel-holes")
    referenced = workspace_replace(
        selected,
        operations=(
            OperationIntent(
                id="op-1", name="drill", kind=OperationKind.DRILL,
                selection_id="sel-holes"),
        ),
    )
    cleared = workspace_replace(referenced, operations=())
    removed = remove_selection(cleared, "sel-holes")
    assert removed.selections == ()


def test_remove_unknown_selection_raises():
    workspace = _workspace()
    with pytest.raises(WorkspaceError, match="unknown selection ID"):
        remove_selection(workspace, "sel-missing")
