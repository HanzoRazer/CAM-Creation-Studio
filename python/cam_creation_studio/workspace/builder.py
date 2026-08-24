"""Build a workspace from imported geometry (CS-011).

Construction generates deterministic :class:`GeometryRef` values in source
order and initializes empty selection / group / operation sets. It does not
transform geometry.
"""

from __future__ import annotations

from ..geometry.models import GeometryCollection
from .errors import WorkspaceError
from .ids import make_workspace_entity_id
from .models import (
    WORKSPACE_VERSION,
    GeometryRef,
    GeometryWorkspace,
)
from .validation import validate_workspace


def build_workspace(collection: GeometryCollection) -> GeometryWorkspace:
    """Wrap ``collection`` in a workspace. Geometry is stored, not copied."""
    refs = []
    seen: set[str] = set()
    for index, entity in enumerate(collection.entities):
        source = getattr(entity, "source", None)
        handle = source.handle if source is not None else None
        ordinal = source.ordinal if source is not None else None
        ref_id = make_workspace_entity_id(index, handle, ordinal)
        if ref_id in seen:
            raise WorkspaceError(
                f"duplicate geometry-ref ID {ref_id!r}")
        seen.add(ref_id)
        refs.append(GeometryRef(id=ref_id, entity_index=index))

    workspace = GeometryWorkspace(
        version=WORKSPACE_VERSION,
        geometry=collection,
        geometry_refs=tuple(refs),
    )
    validate_workspace(workspace)
    return workspace
