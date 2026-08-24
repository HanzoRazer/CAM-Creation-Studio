"""Read-only inspection of workspace geometry (CS-011).

Inspection reports geometry facts, provenance, bounds, and import-fidelity
evidence. It does not interpret those facts as manufacturing intent.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geometry.diagnostics import is_loss
from ..shared.geometry import Bounds
from .models import GeometryWorkspace
from .refs import resolve_entity


@dataclass(frozen=True, slots=True)
class EntityInspection:
    """Descriptive view of one retained workspace entity."""

    id: str
    kind: str
    layer: str
    source_handle: str | None
    source_ordinal: int | None
    bounds: Bounds | None
    diagnostic_codes: tuple[str, ...]
    has_loss: bool


@dataclass(frozen=True, slots=True)
class WorkspaceInspection:
    """Descriptive view of the workspace as a whole."""

    version: str
    entity_count: int
    selection_count: int
    group_count: int
    operation_count: int
    import_loss_count: int
    has_lossy_import: bool


def entity_diagnostics(workspace: GeometryWorkspace, entity_id: str) -> tuple:
    """Diagnostics deterministically attributable to ``entity_id``.

    Attachment requires a non-``None`` diagnostic handle equal to the
    entity's ``source.handle``. Layer and type are not used. Collection-level
    findings (no handle) stay on the collection.
    """
    entity = resolve_entity(workspace, entity_id)
    source = getattr(entity, "source", None)
    if source is None or source.handle is None:
        return ()
    return tuple(
        diagnostic
        for diagnostic in workspace.geometry.diagnostics
        if diagnostic.handle is not None and diagnostic.handle == source.handle
    )


def inspect_entity(
    workspace: GeometryWorkspace, entity_id: str,
) -> EntityInspection:
    """Return a descriptive inspection of one entity."""
    entity = resolve_entity(workspace, entity_id)
    source = getattr(entity, "source", None)
    diagnostics = entity_diagnostics(workspace, entity_id)
    return EntityInspection(
        id=entity_id,
        kind=entity.kind,
        layer=entity.layer,
        source_handle=source.handle if source is not None else None,
        source_ordinal=source.ordinal if source is not None else None,
        bounds=entity.bounds,
        diagnostic_codes=tuple(d.code for d in diagnostics),
        has_loss=any(is_loss(d.code) for d in diagnostics),
    )


def inspect_workspace(workspace: GeometryWorkspace) -> WorkspaceInspection:
    """Return a descriptive inspection of the whole workspace."""
    report = workspace.geometry.report()
    metadata = workspace.geometry.metadata
    return WorkspaceInspection(
        version=workspace.version,
        entity_count=len(workspace.geometry.entities),
        selection_count=len(workspace.selections),
        group_count=len(workspace.groups),
        operation_count=len(workspace.operations),
        import_loss_count=report.loss_count,
        has_lossy_import=bool(metadata and metadata.has_lossy_import),
    )
