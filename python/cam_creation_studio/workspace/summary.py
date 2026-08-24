"""Deterministic workspace summary (CS-011).

Counts only — no wall-clock, no machining readiness, no toolpath claims.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import GeometryWorkspace, OperationKind


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    """Planning-state counts over one workspace."""

    entity_count: int
    selection_count: int
    group_count: int
    operation_count: int
    counts_by_kind: dict[str, int]
    counts_by_operation_kind: dict[str, int]
    import_loss_count: int


def summarize(workspace: GeometryWorkspace) -> WorkspaceSummary:
    """Return deterministic counts for ``workspace``."""
    operation_counts = {kind.value: 0 for kind in OperationKind}
    for operation in workspace.operations:
        operation_counts[operation.kind.value] += 1
    return WorkspaceSummary(
        entity_count=len(workspace.geometry.entities),
        selection_count=len(workspace.selections),
        group_count=len(workspace.groups),
        operation_count=len(workspace.operations),
        counts_by_kind=workspace.geometry.counts(),
        counts_by_operation_kind=operation_counts,
        import_loss_count=workspace.geometry.report().loss_count,
    )
