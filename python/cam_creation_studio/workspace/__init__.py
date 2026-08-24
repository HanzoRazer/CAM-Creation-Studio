"""Geometry workspace: the first authorized consumer of neutral geometry (CS-011).

Load a :class:`~cam_creation_studio.geometry.models.GeometryCollection` into an
inspectable workspace, select and group entities, and record non-executable
operation intent. No toolpaths, feeds/speeds, or G-code are produced here.
"""

from __future__ import annotations

from .builder import build_workspace
from .errors import WorkspaceError
from .ids import make_workspace_entity_id, make_workspace_object_id
from .inspection import (
    EntityInspection,
    WorkspaceInspection,
    entity_diagnostics,
    inspect_entity,
    inspect_workspace,
)
from .models import (
    WORKSPACE_VERSION,
    GeometryGroup,
    GeometryRef,
    GeometrySelection,
    GeometryWorkspace,
    OperationIntent,
    OperationKind,
)
from .refs import resolve_entity, resolve_selection
from .validation import validate_workspace

__all__ = [
    "WORKSPACE_VERSION",
    "EntityInspection",
    "GeometryGroup",
    "GeometryRef",
    "GeometrySelection",
    "GeometryWorkspace",
    "OperationIntent",
    "OperationKind",
    "WorkspaceError",
    "WorkspaceInspection",
    "build_workspace",
    "entity_diagnostics",
    "inspect_entity",
    "inspect_workspace",
    "make_workspace_entity_id",
    "make_workspace_object_id",
    "resolve_entity",
    "resolve_selection",
    "validate_workspace",
]
