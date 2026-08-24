"""Structural validation for a geometry workspace (CS-011).

This checks referential integrity and schema identity only. It does not
judge whether an operation kind is a sensible machining choice for a
shape, and it does not emit advisory import diagnostics.
"""

from __future__ import annotations

from .errors import WorkspaceError
from .models import WORKSPACE_VERSION, GeometryWorkspace, OperationKind


def validate_workspace(workspace: GeometryWorkspace) -> None:
    """Raise :class:`WorkspaceError` if ``workspace`` is structurally invalid.

    Returns ``None`` when the document is valid. This is the only validation
    authority — helpers and deserialization call it; there is no findings list.
    """
    if workspace.version != WORKSPACE_VERSION:
        raise WorkspaceError(
            f"unknown workspace version {workspace.version!r}; "
            f"expected {WORKSPACE_VERSION!r}")

    entities = workspace.geometry.entities
    refs = workspace.geometry_refs
    if len(refs) != len(entities):
        raise WorkspaceError(
            f"geometry_refs count {len(refs)} does not match entity count "
            f"{len(entities)}")

    expected_indexes = list(range(len(entities)))
    got_indexes = [ref.entity_index for ref in refs]
    if got_indexes != expected_indexes:
        raise WorkspaceError(
            f"geometry_refs must be in source order {expected_indexes}, "
            f"got {got_indexes}")

    entity_ids: set[str] = set()
    for ref in refs:
        if ref.id in entity_ids:
            raise WorkspaceError(f"duplicate geometry-ref ID {ref.id!r}")
        if not ref.id:
            raise WorkspaceError("geometry-ref ID must not be empty")
        entity_ids.add(ref.id)

    selection_ids = _validate_named_member_lists(
        workspace.selections, "selection", entity_ids)
    _validate_named_member_lists(workspace.groups, "group", entity_ids)
    _validate_operations(workspace, selection_ids)


def _validate_named_member_lists(items, kind: str, entity_ids: set[str]) -> set[str]:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise WorkspaceError(f"duplicate {kind} ID {item.id!r}")
        if not item.id:
            raise WorkspaceError(f"{kind} ID must not be empty")
        seen.add(item.id)
        if not item.entity_ids:
            raise WorkspaceError(f"{kind} {item.id!r} is empty")
        if len(item.entity_ids) != len(set(item.entity_ids)):
            raise WorkspaceError(
                f"{kind} {item.id!r} contains duplicate entity IDs")
        for entity_id in item.entity_ids:
            if entity_id not in entity_ids:
                raise WorkspaceError(
                    f"{kind} {item.id!r} references missing entity "
                    f"{entity_id!r}")
    return seen


def _validate_operations(
    workspace: GeometryWorkspace, selection_ids: set[str],
) -> None:
    seen: set[str] = set()
    for operation in workspace.operations:
        if operation.id in seen:
            raise WorkspaceError(f"duplicate operation ID {operation.id!r}")
        if not operation.id:
            raise WorkspaceError("operation ID must not be empty")
        seen.add(operation.id)
        if not isinstance(operation.kind, OperationKind):
            raise WorkspaceError(
                f"operation {operation.id!r} has unknown kind "
                f"{operation.kind!r}")
        if operation.selection_id not in selection_ids:
            raise WorkspaceError(
                f"operation {operation.id!r} references missing selection "
                f"{operation.selection_id!r}")
