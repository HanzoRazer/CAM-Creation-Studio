"""Advisory feeds/speeds generation for a bound machining operation (CS-014).

Delegates every machining number to the existing calculator. This module
does not invent DOC, WOC, stepdown, or stepover, and does not treat
``target_depth_mm`` as depth of cut.
"""

from __future__ import annotations

import json
from dataclasses import replace

from ..feeds_speeds.calculator import FeedRecommendation, calculate_feeds
from .enums import RecommendationStatus
from .errors import RecommendationError
from .ids import make_recommendation_id
from .models import OperationFeedRecommendation
from .plan import OPERATION_PLAN_V3, OperationPlan, validate_operation_plan
from .resolution import RecommendationInputs, resolve_recommendation_inputs


def calculate_advisory_feeds(
    inputs: RecommendationInputs,
) -> FeedRecommendation:
    """Call the canonical calculator with resolved catalog inputs.

    Passes tool diameter, flute count, requested ``spindle_rpm``, and
    material id. Passes ``max_rpm`` only when the machine profile has a
    ceiling. Never supplies ``doc_mm``, ``woc_mm``, ``feed_override``, or
    ``max_power_kw``.
    """
    kwargs: dict = {
        "tool_diameter_mm": inputs.tool.diameter_mm,
        "flutes": inputs.tool.flutes,
        "spindle_rpm": inputs.spindle_rpm,
        "material": inputs.material.id,
    }
    if inputs.machine.max_rpm is not None:
        kwargs["max_rpm"] = inputs.machine.max_rpm
    try:
        return calculate_feeds(**kwargs)
    except ValueError as exc:
        raise RecommendationError(str(exc)) from exc


def feed_input_fingerprint(inputs: RecommendationInputs) -> str:
    """Deterministic fingerprint of calculation-driving primitives.

    Presentation fields (labels, notes) are omitted. No timestamps.
    """
    payload = {
        "binding_id": inputs.binding.id,
        "definition_id": inputs.definition.id,
        "machine_max_rpm": inputs.machine.max_rpm,
        "machine_profile_id": inputs.machine.id,
        "material_chipload_mm": [
            inputs.material.chipload_mm[0],
            inputs.material.chipload_mm[1],
        ],
        "material_id": inputs.material.id,
        "spindle_rpm": inputs.spindle_rpm,
        "tool_diameter_mm": inputs.tool.diameter_mm,
        "tool_flutes": inputs.tool.flutes,
        "tool_id": inputs.tool.id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def recommendation_for_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationFeedRecommendation | None:
    """Return the stored recommendation for ``definition_id``, or ``None``."""
    for item in plan.recommendations:
        if item.definition_id == definition_id:
            return item
    return None


def recommend_feeds_speeds(
    plan: OperationPlan,
    definition_id: str,
    machine_profile_id: str,
    spindle_rpm: object,
    *,
    id: str | None = None,
) -> OperationPlan:
    """Create one advisory recommendation. Rejected if one already exists."""
    existing = recommendation_for_definition(plan, definition_id)
    if existing is not None:
        raise RecommendationError(
            f"definition {definition_id!r} already has a feed recommendation "
            f"{existing.id!r}")
    wrapper = _build_recommendation(
        plan, definition_id, machine_profile_id, spindle_rpm, id=id)
    updated = replace(
        plan,
        version=OPERATION_PLAN_V3,
        recommendations=plan.recommendations + (wrapper,),
    )
    validate_operation_plan(updated)
    return updated


def replace_feed_recommendation(
    plan: OperationPlan,
    recommendation_id: str,
    machine_profile_id: str,
    spindle_rpm: object,
) -> OperationPlan:
    """Recalculate one recommendation. ID and definition_id are preserved."""
    current = _resolve_recommendation(plan, recommendation_id)
    rebuilt = _build_recommendation(
        plan,
        current.definition_id,
        machine_profile_id,
        spindle_rpm,
        id=recommendation_id,
    )
    recommendations = tuple(
        rebuilt if item.id == recommendation_id else item
        for item in plan.recommendations
    )
    updated = replace(
        plan,
        version=OPERATION_PLAN_V3,
        recommendations=recommendations,
    )
    validate_operation_plan(updated)
    return updated


def remove_feed_recommendation(
    plan: OperationPlan, recommendation_id: str,
) -> OperationPlan:
    """Remove one recommendation. Definition and binding remain."""
    _resolve_recommendation(plan, recommendation_id)
    recommendations = tuple(
        item for item in plan.recommendations if item.id != recommendation_id)
    updated = replace(plan, recommendations=recommendations)
    validate_operation_plan(updated)
    return updated


def recommendation_status(
    plan: OperationPlan,
    definition_id: str,
    *,
    machine_profile_id: str | None = None,
) -> RecommendationStatus:
    """Describe stored advice. Does not invoke the calculator."""
    stored = recommendation_for_definition(plan, definition_id)
    if stored is None:
        return RecommendationStatus.MISSING
    if (
        machine_profile_id is not None
        and machine_profile_id != stored.machine_profile_id
    ):
        return RecommendationStatus.STALE
    current = feed_input_fingerprint(resolve_recommendation_inputs(
        plan, stored.definition_id, stored.machine_profile_id,
        stored.spindle_rpm))
    if current != stored.input_fingerprint:
        return RecommendationStatus.STALE
    return RecommendationStatus.CURRENT


def _build_recommendation(
    plan: OperationPlan,
    definition_id: str,
    machine_profile_id: str,
    spindle_rpm: object,
    *,
    id: str | None,
) -> OperationFeedRecommendation:
    inputs = resolve_recommendation_inputs(
        plan, definition_id, machine_profile_id, spindle_rpm)
    fingerprint = feed_input_fingerprint(inputs)
    recommendation_id = id if id is not None else make_recommendation_id(
        inputs.definition.id,
        inputs.binding.id,
        inputs.machine.id,
        fingerprint,
    )
    if not recommendation_id:
        raise RecommendationError("recommendation ID must not be empty")
    return OperationFeedRecommendation(
        id=recommendation_id,
        definition_id=inputs.definition.id,
        binding_id=inputs.binding.id,
        machine_profile_id=inputs.machine.id,
        spindle_rpm=inputs.spindle_rpm,
        input_fingerprint=fingerprint,
        recommendation=calculate_advisory_feeds(inputs),
    )


def _resolve_recommendation(
    plan: OperationPlan, recommendation_id: str,
) -> OperationFeedRecommendation:
    for item in plan.recommendations:
        if item.id == recommendation_id:
            return item
    raise RecommendationError(f"unknown recommendation ID {recommendation_id!r}")
