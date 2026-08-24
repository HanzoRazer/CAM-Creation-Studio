"""Named organizational groups over workspace geometry (CS-011)."""

from __future__ import annotations

from .ids import make_workspace_object_id
from .members import as_entity_ids
from .models import GeometryGroup, GeometryWorkspace
from .refs import resolve_group, workspace_replace
from .validation import validate_workspace


def create_group(
    workspace: GeometryWorkspace,
    name: str,
    entity_ids,
    *,
    description: str = "",
    id: str | None = None,
) -> GeometryWorkspace:
    """Add a named group. Empty groups and duplicate members are rejected."""
    members = as_entity_ids(entity_ids, "group")
    group_id = id if id is not None else make_workspace_object_id(
        "group", name, *members, existing_count=len(workspace.groups),
    )
    group = GeometryGroup(
        id=group_id, name=name, entity_ids=members, description=description)
    updated = workspace_replace(
        workspace, groups=workspace.groups + (group,))
    validate_workspace(updated)
    return updated


def replace_group(
    workspace: GeometryWorkspace,
    group_id: str,
    name: str,
    entity_ids,
    *,
    description: str = "",
) -> GeometryWorkspace:
    """Replace one group's name, members, and description. The ID is unchanged."""
    resolve_group(workspace, group_id)
    members = as_entity_ids(entity_ids, "group")
    replacement = GeometryGroup(
        id=group_id, name=name, entity_ids=members, description=description)
    groups = tuple(
        replacement if item.id == group_id else item
        for item in workspace.groups
    )
    updated = workspace_replace(workspace, groups=groups)
    validate_workspace(updated)
    return updated


def remove_group(
    workspace: GeometryWorkspace, group_id: str,
) -> GeometryWorkspace:
    """Remove a group. Groups have no dependents."""
    resolve_group(workspace, group_id)
    groups = tuple(item for item in workspace.groups if item.id != group_id)
    updated = workspace_replace(workspace, groups=groups)
    validate_workspace(updated)
    return updated
