"""Deterministic operation-plan summary (CS-012).

Counts only — no machining recommendations, no toolpath claims, and no
readiness judgement. Tools are intentionally out of scope; a count of
definitions without tool assignment is descriptive, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    ContourDefinition,
    OperationDefinition,
    PocketDefinition,
    ReferenceDefinition,
    definition_type_name,
)
from .plan import OperationPlan

_TYPE_KEYS = (
    "contour", "pocket", "drill", "engrave", "slot", "reference",
)


@dataclass(frozen=True, slots=True)
class OperationPlanSummary:
    """Planning-state counts over one operation plan."""

    definition_count: int
    counts_by_type: dict[str, int]
    referenced_selection_count: int
    declared_depth_count: int
    allowance_count: int
    definitions_without_tool_count: int


def summarize_operation_plan(plan: OperationPlan) -> OperationPlanSummary:
    """Return deterministic counts for ``plan``. Tools are not assigned in v1."""
    counts = {key: 0 for key in _TYPE_KEYS}
    depth_count = 0
    allowance_count = 0
    selection_ids: set[str] = set()
    intents = {intent.id: intent for intent in plan.workspace.operations}
    for definition in plan.definitions:
        counts[definition_type_name(definition)] += 1
        if not isinstance(definition, ReferenceDefinition):
            depth_count += 1
        if _has_allowance(definition):
            allowance_count += 1
        intent = intents.get(definition.intent_id)
        if intent is not None:
            selection_ids.add(intent.selection_id)
    return OperationPlanSummary(
        definition_count=len(plan.definitions),
        counts_by_type=counts,
        referenced_selection_count=len(selection_ids),
        declared_depth_count=depth_count,
        allowance_count=allowance_count,
        definitions_without_tool_count=len(plan.definitions),
    )


def _has_allowance(definition: OperationDefinition) -> bool:
    if isinstance(definition, ContourDefinition):
        return definition.stock_allowance_mm is not None
    if isinstance(definition, PocketDefinition):
        return (
            definition.wall_allowance_mm is not None
            or definition.floor_allowance_mm is not None
        )
    return False
