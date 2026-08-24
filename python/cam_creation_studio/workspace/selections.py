"""Named selections over workspace geometry (CS-011)."""

from __future__ import annotations

from .errors import WorkspaceError
from .ids import make_workspace_object_id
from .members import as_entity_ids
from .models import GeometrySelection, GeometryWorkspace
from .refs import resolve_selection, workspace_replace
from .validation import validate_workspace


def create_selection(
    workspace: GeometryWorkspace,
    name: str,
    entity_ids,
    *,
    id: str | None = None,
) -> GeometryWorkspace:
    """Add a named selection. Empty and duplicate members are rejected."""
    members = as_entity_ids(entity_ids, "selection")
    selection_id = id if id is not None else make_workspace_object_id(
        "selection", name, *members, existing_count=len(workspace.selections),
    )
    selection = GeometrySelection(
        id=selection_id, name=name, entity_ids=members)
    updated = workspace_replace(
        workspace, selections=workspace.selections + (selection,))
    validate_workspace(updated)
    return updated


def replace_selection(
    workspace: GeometryWorkspace,
    selection_id: str,
    name: str,
    entity_ids,
) -> GeometryWorkspace:
    """Replace one selection's name and members. The ID is unchanged."""
    resolve_selection(workspace, selection_id)
    members = as_entity_ids(entity_ids, "selection")
    replacement = GeometrySelection(
        id=selection_id, name=name, entity_ids=members)
    selections = tuple(
        replacement if item.id == selection_id else item
        for item in workspace.selections
    )
    updated = workspace_replace(workspace, selections=selections)
    validate_workspace(updated)
    return updated


def remove_selection(
    workspace: GeometryWorkspace, selection_id: str,
) -> GeometryWorkspace:
    """Remove a selection. Rejected when any operation still references it."""
    resolve_selection(workspace, selection_id)
    dependents = [
        operation.id
        for operation in workspace.operations
        if operation.selection_id == selection_id
    ]
    if dependents:
        raise WorkspaceError(
            f"cannot remove selection {selection_id!r}: referenced by "
            f"operations {dependents}")
    selections = tuple(
        item for item in workspace.selections if item.id != selection_id)
    updated = workspace_replace(workspace, selections=selections)
    validate_workspace(updated)
    return updated
