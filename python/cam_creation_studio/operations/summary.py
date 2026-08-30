"""Deterministic operation-plan summary (CS-012–CS-014).

Counts only — no wall-clock, no toolpath claims, and no readiness
judgement. CS-012 ``OperationPlanSummary`` remains definition-oriented.
CS-013 ``BindingSummary`` reports bound vs unbound state without scoring
quality. CS-014 ``FeedRecommendationSummary`` reports current/stale/missing
advisory recommendations without a safety or readiness score.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..feeds_speeds.materials import list_materials
from ..feeds_speeds.tools import list_tools
from .enums import RecommendationStatus
from .models import (
    ContourDefinition,
    OperationDefinition,
    PocketDefinition,
    ReferenceDefinition,
    definition_type_name,
)
from .plan import OperationPlan
from .recommendations import recommendation_status
from .resolution import resolve_material, resolve_tool

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


@dataclass(frozen=True, slots=True)
class BindingSummary:
    """Binding-state counts. Unbound is incomplete context, not an error."""

    definition_count: int
    bound_definition_count: int
    unbound_definition_count: int
    counts_by_tool_kind: dict[str, int]
    counts_by_material: dict[str, int]


def summarize_bindings(plan: OperationPlan) -> BindingSummary:
    """Return bound/unbound counts. No suitability score or ready flag."""
    kind_counts = {tool.kind: 0 for tool in list_tools()}
    material_counts = {material.id: 0 for material in list_materials()}
    for binding in plan.bindings:
        kind_counts[resolve_tool(binding).kind] += 1
        material_counts[resolve_material(binding).id] += 1
    bound = len(plan.bindings)
    return BindingSummary(
        definition_count=len(plan.definitions),
        bound_definition_count=bound,
        unbound_definition_count=len(plan.definitions) - bound,
        counts_by_tool_kind=kind_counts,
        counts_by_material=material_counts,
    )


@dataclass(frozen=True, slots=True)
class FeedRecommendationSummary:
    """Recommendation-state counts. No readiness or quality score."""

    machining_definition_count: int
    bound_definition_count: int
    recommendation_count: int
    current_count: int
    stale_count: int
    missing_count: int
    warning_count: int


def summarize_feed_recommendations(plan: OperationPlan) -> FeedRecommendationSummary:
    """Count current/stale/missing advice. Does not recalculate feeds."""
    machining = [
        definition for definition in plan.definitions
        if not isinstance(definition, ReferenceDefinition)
    ]
    current = 0
    stale = 0
    missing = 0
    for definition in machining:
        status = recommendation_status(plan, definition.id)
        if status is RecommendationStatus.CURRENT:
            current += 1
        elif status is RecommendationStatus.STALE:
            stale += 1
        else:
            missing += 1
    warning_count = 0
    for item in plan.recommendations:
        warning_count += sum(
            1
            for diagnostic in item.recommendation.diagnostics
            if diagnostic.severity in {"warning", "danger"}
        )
    return FeedRecommendationSummary(
        machining_definition_count=len(machining),
        bound_definition_count=len(plan.bindings),
        recommendation_count=len(plan.recommendations),
        current_count=current,
        stale_count=stale,
        missing_count=missing,
        warning_count=warning_count,
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
