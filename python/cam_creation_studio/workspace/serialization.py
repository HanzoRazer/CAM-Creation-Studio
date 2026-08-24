"""Versioned JSON for a geometry workspace (CS-011).

The document is a workspace, not a bare :class:`GeometryCollection`. Geometry
is embedded via the collection's own serializer so heterogeneous entities
round-trip. Unknown versions and operation kinds fail as
:class:`WorkspaceError`.
"""

from __future__ import annotations

import json

from ..geometry.models import GeometryCollection
from .errors import WorkspaceError
from .models import (
    WORKSPACE_VERSION,
    GeometryGroup,
    GeometryRef,
    GeometrySelection,
    GeometryWorkspace,
    OperationIntent,
    OperationKind,
)
from .validation import validate_workspace


def workspace_to_dict(workspace: GeometryWorkspace) -> dict:
    """JSON-ready document. No timestamps; order is document order."""
    return {
        "version": workspace.version,
        "geometry": workspace.geometry.to_dict(),
        "geometry_refs": [
            {"id": ref.id, "entity_index": ref.entity_index}
            for ref in workspace.geometry_refs
        ],
        "selections": [
            {
                "id": selection.id,
                "name": selection.name,
                "entity_ids": list(selection.entity_ids),
            }
            for selection in workspace.selections
        ],
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "entity_ids": list(group.entity_ids),
                "description": group.description,
            }
            for group in workspace.groups
        ],
        "operations": [
            {
                "id": operation.id,
                "name": operation.name,
                "kind": operation.kind.value,
                "selection_id": operation.selection_id,
            }
            for operation in workspace.operations
        ],
    }


def workspace_from_dict(data: object) -> GeometryWorkspace:
    """Rebuild a workspace and structurally validate it."""
    if not isinstance(data, dict):
        raise WorkspaceError("workspace document must be an object")
    if "version" not in data:
        raise WorkspaceError(
            "not a workspace document: missing version "
            f"{WORKSPACE_VERSION!r}")
    version = data["version"]
    if version != WORKSPACE_VERSION:
        raise WorkspaceError(
            f"unknown workspace version {version!r}; "
            f"expected {WORKSPACE_VERSION!r}")

    raw_geometry = data.get("geometry")
    if not isinstance(raw_geometry, dict):
        raise WorkspaceError("workspace geometry payload is missing or malformed")
    try:
        geometry = GeometryCollection.from_dict(raw_geometry)
    except (TypeError, ValueError, KeyError) as exc:
        raise WorkspaceError(
            f"malformed workspace geometry: {exc}") from exc

    workspace = GeometryWorkspace(
        version=version,
        geometry=geometry,
        geometry_refs=_refs(data.get("geometry_refs")),
        selections=_selections(data.get("selections", [])),
        groups=_groups(data.get("groups", [])),
        operations=_operations(data.get("operations", [])),
    )
    validate_workspace(workspace)
    return workspace


def workspace_to_json(
    workspace: GeometryWorkspace,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """Deterministic JSON: no wall-clock fields; keys sorted by default."""
    return json.dumps(
        workspace_to_dict(workspace), indent=indent, sort_keys=sort_keys)


def workspace_from_json(text: str) -> GeometryWorkspace:
    """Parse JSON and rebuild a validated workspace."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"malformed workspace JSON: {exc}") from exc
    return workspace_from_dict(data)


def _expect_list(value: object, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise WorkspaceError(f"{field} must be a list")
    return value


def _expect_object(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise WorkspaceError(f"malformed {field}")
    return value


def _field(item: dict, name: str, field: str):
    if name not in item:
        raise WorkspaceError(f"{field} is missing {name!r}")
    return item[name]


def _refs(value: object) -> tuple[GeometryRef, ...]:
    if value is None:
        raise WorkspaceError("geometry_refs is missing")
    refs = []
    for item in _expect_list(value, "geometry_refs"):
        raw = _expect_object(item, "geometry_ref")
        refs.append(GeometryRef(
            id=_field(raw, "id", "geometry_ref"),
            entity_index=_field(raw, "entity_index", "geometry_ref"),
        ))
    return tuple(refs)


def _entity_ids(raw: dict, field: str) -> tuple[str, ...]:
    value = _field(raw, "entity_ids", field)
    if not isinstance(value, list):
        raise WorkspaceError(f"{field} entity_ids must be a list")
    return tuple(value)


def _selections(value: object) -> tuple[GeometrySelection, ...]:
    selections = []
    for item in _expect_list(value, "selections"):
        raw = _expect_object(item, "selection")
        selections.append(GeometrySelection(
            id=_field(raw, "id", "selection"),
            name=_field(raw, "name", "selection"),
            entity_ids=_entity_ids(raw, "selection"),
        ))
    return tuple(selections)


def _groups(value: object) -> tuple[GeometryGroup, ...]:
    groups = []
    for item in _expect_list(value, "groups"):
        raw = _expect_object(item, "group")
        groups.append(GeometryGroup(
            id=_field(raw, "id", "group"),
            name=_field(raw, "name", "group"),
            entity_ids=_entity_ids(raw, "group"),
            description=raw.get("description", ""),
        ))
    return tuple(groups)


def _operations(value: object) -> tuple[OperationIntent, ...]:
    operations = []
    for item in _expect_list(value, "operations"):
        raw = _expect_object(item, "operation")
        kind_value = _field(raw, "kind", "operation")
        try:
            kind = OperationKind(kind_value)
        except ValueError as exc:
            raise WorkspaceError(
                f"unknown operation kind {kind_value!r}") from exc
        operations.append(OperationIntent(
            id=_field(raw, "id", "operation"),
            name=_field(raw, "name", "operation"),
            kind=kind,
            selection_id=_field(raw, "selection_id", "operation"),
        ))
    return tuple(operations)
