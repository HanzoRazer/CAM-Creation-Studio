"""Non-executable operation intent on a selection (CS-011)."""

from __future__ import annotations

from .errors import WorkspaceError
from .ids import make_workspace_object_id
from .models import GeometryWorkspace, OperationIntent, OperationKind
from .refs import resolve_operation, workspace_replace
from .validation import validate_workspace


def _coerce_kind(kind: OperationKind | str) -> OperationKind:
    if isinstance(kind, OperationKind):
        return kind
    try:
        return OperationKind(kind)
    except ValueError as exc:
        raise WorkspaceError(f"unknown operation kind {kind!r}") from exc


def assign_operation(
    workspace: GeometryWorkspace,
    name: str,
    kind: OperationKind | str,
    selection_id: str,
    *,
    id: str | None = None,
) -> GeometryWorkspace:
    """Attach an operation category to a selection. No machining fields."""
    resolved_kind = _coerce_kind(kind)
    operation_id = id if id is not None else make_workspace_object_id(
        "operation", name, selection_id,
        existing_count=len(workspace.operations),
    )
    operation = OperationIntent(
        id=operation_id, name=name, kind=resolved_kind,
        selection_id=selection_id)
    updated = workspace_replace(
        workspace, operations=workspace.operations + (operation,))
    validate_workspace(updated)
    return updated


def replace_operation(
    workspace: GeometryWorkspace,
    operation_id: str,
    name: str,
    kind: OperationKind | str,
    selection_id: str,
) -> GeometryWorkspace:
    """Replace one operation's name, kind, and selection. The ID is unchanged."""
    resolve_operation(workspace, operation_id)
    replacement = OperationIntent(
        id=operation_id, name=name, kind=_coerce_kind(kind),
        selection_id=selection_id)
    operations = tuple(
        replacement if item.id == operation_id else item
        for item in workspace.operations
    )
    updated = workspace_replace(workspace, operations=operations)
    validate_workspace(updated)
    return updated


def remove_operation(
    workspace: GeometryWorkspace, operation_id: str,
) -> GeometryWorkspace:
    """Remove an operation intent."""
    resolve_operation(workspace, operation_id)
    operations = tuple(
        item for item in workspace.operations if item.id != operation_id)
    updated = workspace_replace(workspace, operations=operations)
    validate_workspace(updated)
    return updated
