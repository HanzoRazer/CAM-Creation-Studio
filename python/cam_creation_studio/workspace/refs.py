"""Resolve and replace helpers for an immutable workspace (CS-011)."""

from __future__ import annotations

from dataclasses import replace

from ..geometry.models import Entity
from .errors import WorkspaceError
from .models import GeometryGroup, GeometrySelection, GeometryWorkspace, OperationIntent


def resolve_entity(workspace: GeometryWorkspace, entity_id: str) -> Entity:
    """Return the imported entity for ``entity_id``, or raise."""
    for ref in workspace.geometry_refs:
        if ref.id == entity_id:
            return workspace.geometry.entities[ref.entity_index]
    raise WorkspaceError(f"unknown geometry ID {entity_id!r}")


def resolve_selection(
    workspace: GeometryWorkspace, selection_id: str,
) -> GeometrySelection:
    """Return the named selection, or raise."""
    for selection in workspace.selections:
        if selection.id == selection_id:
            return selection
    raise WorkspaceError(f"unknown selection ID {selection_id!r}")


def resolve_group(workspace: GeometryWorkspace, group_id: str) -> GeometryGroup:
    """Return the named group, or raise."""
    for group in workspace.groups:
        if group.id == group_id:
            return group
    raise WorkspaceError(f"unknown group ID {group_id!r}")


def resolve_operation(
    workspace: GeometryWorkspace, operation_id: str,
) -> OperationIntent:
    """Return the named operation intent, or raise."""
    for operation in workspace.operations:
        if operation.id == operation_id:
            return operation
    raise WorkspaceError(f"unknown operation ID {operation_id!r}")


def workspace_replace(
    workspace: GeometryWorkspace, **changes,
) -> GeometryWorkspace:
    """Return a new workspace with the given fields replaced."""
    return replace(workspace, **changes)
