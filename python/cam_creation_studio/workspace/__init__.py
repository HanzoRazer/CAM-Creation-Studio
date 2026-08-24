"""Geometry workspace: the first authorized consumer of neutral geometry (CS-011).

Load a :class:`~cam_creation_studio.geometry.models.GeometryCollection` into an
inspectable workspace, select and group entities, and record non-executable
operation intent. No toolpaths, feeds/speeds, or G-code are produced here.
"""

from __future__ import annotations

from .builder import build_workspace
from .errors import WorkspaceError
from .groups import create_group, remove_group, replace_group
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
from .operations import assign_operation, remove_operation, replace_operation
from .refs import (
    resolve_entity,
    resolve_group,
    resolve_operation,
    resolve_selection,
)
from .selections import create_selection, remove_selection, replace_selection
from .serialization import (
    workspace_from_dict,
    workspace_from_json,
    workspace_to_dict,
    workspace_to_json,
)
from .summary import WorkspaceSummary, summarize
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
    "WorkspaceSummary",
    "assign_operation",
    "build_workspace",
    "create_group",
    "create_selection",
    "entity_diagnostics",
    "inspect_entity",
    "inspect_workspace",
    "make_workspace_entity_id",
    "make_workspace_object_id",
    "remove_group",
    "remove_operation",
    "remove_selection",
    "replace_group",
    "replace_operation",
    "replace_selection",
    "resolve_entity",
    "resolve_group",
    "resolve_operation",
    "resolve_selection",
    "summarize",
    "validate_workspace",
    "workspace_from_dict",
    "workspace_from_json",
    "workspace_to_dict",
    "workspace_to_json",
]
