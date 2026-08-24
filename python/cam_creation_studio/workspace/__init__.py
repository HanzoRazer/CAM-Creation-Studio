"""Geometry workspace: the first authorized consumer of neutral geometry (CS-011).

Load a :class:`~cam_creation_studio.geometry.models.GeometryCollection` into an
inspectable workspace, select and group entities, and record non-executable
operation intent. No toolpaths, feeds/speeds, or G-code are produced here.
"""

from __future__ import annotations

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

__all__ = [
    "WORKSPACE_VERSION",
    "GeometryGroup",
    "GeometryRef",
    "GeometrySelection",
    "GeometryWorkspace",
    "OperationIntent",
    "OperationKind",
    "WorkspaceError",
]
