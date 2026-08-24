"""Resolve and replace helpers for an immutable workspace (CS-011)."""

from __future__ import annotations

from dataclasses import replace

from ..geometry.models import Entity
from .errors import WorkspaceError
from .models import GeometrySelection, GeometryWorkspace


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


def workspace_replace(
    workspace: GeometryWorkspace, **changes,
) -> GeometryWorkspace:
    """Return a new workspace with the given fields replaced."""
    return replace(workspace, **changes)
