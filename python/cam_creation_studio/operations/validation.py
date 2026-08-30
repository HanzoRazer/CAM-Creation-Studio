"""Structural and dimensional validation for operation definitions (CS-012).

This checks referential integrity, intent/definition kind agreement, and
dimensional field contracts. It does not judge whether an operation kind is
a sensible machining choice for a shape.
"""

from __future__ import annotations

import math

from ..feeds_speeds.calculator import FeedRecommendation
from ..workspace.models import GeometryWorkspace, OperationIntent, OperationKind
from .enums import ContourRelation, CutDirection, SlotRelation
from .errors import BindingError, OperationDefinitionError, RecommendationError
from .models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationBinding,
    OperationDefinition,
    OperationFeedRecommendation,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
)
from .resolution import (
    require_bindable_definition,
    resolve_machine_profile,
    resolve_material,
    resolve_tool,
    validate_spindle_rpm,
)

_KIND_FOR_TYPE = {
    ContourDefinition: OperationKind.CONTOUR,
    PocketDefinition: OperationKind.POCKET,
    DrillDefinition: OperationKind.DRILL,
    EngraveDefinition: OperationKind.ENGRAVE,
    SlotDefinition: OperationKind.SLOT,
    ReferenceDefinition: OperationKind.REFERENCE,
}


def resolve_intent(
    workspace: GeometryWorkspace, intent_id: str,
) -> OperationIntent:
    """Return the CS-011 intent for ``intent_id``, or raise."""
    for intent in workspace.operations:
        if intent.id == intent_id:
            return intent
    raise OperationDefinitionError(
        f"unknown operation intent {intent_id!r}")


def require_intent_kind(
    intent: OperationIntent, expected: OperationKind,
) -> None:
    """Raise if ``intent.kind`` is not ``expected``."""
    if intent.kind is not expected:
        raise OperationDefinitionError(
            f"definition requires {expected.value} intent; "
            f"{intent.id!r} is {intent.kind.value}")


def validate_positive_distance(name: str, value: object) -> float:
    """Require a finite millimetre magnitude strictly greater than zero."""
    number = _require_finite(name, value)
    if number <= 0:
        raise OperationDefinitionError(
            f"{name} must be greater than 0 mm, got {number}")
    return number


def validate_optional_positive_distance(
    name: str, value: object,
) -> float | None:
    """``None`` (unspecified) or a finite millimetre magnitude ``> 0``."""
    if value is None:
        return None
    return validate_positive_distance(name, value)


def validate_nonnegative_optional_distance(
    name: str, value: object,
) -> float | None:
    """``None`` (unspecified) or a finite millimetre magnitude ``>= 0``."""
    if value is None:
        return None
    number = _require_finite(name, value)
    if number < 0:
        raise OperationDefinitionError(
            f"{name} must be greater than or equal to 0 mm, got {number}")
    return number


def validate_operation_definition(
    workspace: GeometryWorkspace,
    definition: OperationDefinition,
) -> None:
    """Raise if ``definition`` is structurally or dimensionally invalid.

    Returns ``None`` when the document is valid. Geometry suitability is
    not assessed: a ``DRILL`` on a line remains structurally accepted.
    """
    if not isinstance(definition, tuple(_KIND_FOR_TYPE)):
        raise OperationDefinitionError(
            f"unknown operation-definition type {type(definition)!r}")
    if not definition.id:
        raise OperationDefinitionError("definition ID must not be empty")
    if not definition.intent_id:
        raise OperationDefinitionError("intent_id must not be empty")

    intent = resolve_intent(workspace, definition.intent_id)
    require_intent_kind(intent, _KIND_FOR_TYPE[type(definition)])
    _validate_dimensions(definition)


def validate_operation_definitions(
    workspace: GeometryWorkspace,
    definitions: tuple[OperationDefinition, ...],
) -> None:
    """Validate a collection: unique IDs, one definition per intent, each valid."""
    seen_ids: set[str] = set()
    seen_intents: set[str] = set()
    for definition in definitions:
        if definition.id in seen_ids:
            raise OperationDefinitionError(
                f"duplicate definition ID {definition.id!r}")
        seen_ids.add(definition.id)
        if definition.intent_id in seen_intents:
            raise OperationDefinitionError(
                f"intent {definition.intent_id!r} already has a definition")
        seen_intents.add(definition.intent_id)
        validate_operation_definition(workspace, definition)


def validate_operation_bindings(
    definitions: tuple[OperationDefinition, ...],
    bindings: tuple[OperationBinding, ...],
) -> None:
    """Validate binding IDs, one-binding-per-definition, and catalog refs.

    Unbound machining definitions are valid. ``REFERENCE`` definitions
    cannot be bound. Suitability is not judged.
    """
    definition_by_id = {item.id: item for item in definitions}
    seen_ids: set[str] = set()
    seen_definitions: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, OperationBinding):
            raise BindingError(
                f"unknown binding type {type(binding)!r}")
        if not binding.id:
            raise BindingError("binding ID must not be empty")
        if binding.id in seen_ids:
            raise BindingError(f"duplicate binding ID {binding.id!r}")
        seen_ids.add(binding.id)
        if not binding.definition_id:
            raise BindingError("binding definition_id must not be empty")
        if binding.definition_id in seen_definitions:
            raise BindingError(
                f"definition {binding.definition_id!r} already has a binding")
        seen_definitions.add(binding.definition_id)
        definition = definition_by_id.get(binding.definition_id)
        if definition is None:
            raise BindingError(
                f"unknown definition ID {binding.definition_id!r}")
        require_bindable_definition(definition)
        if not binding.tool_id:
            raise BindingError("tool_id must not be empty")
        if not binding.material_id:
            raise BindingError("material_id must not be empty")
        resolve_tool(binding)
        resolve_material(binding)


def validate_operation_recommendations(
    definitions: tuple[OperationDefinition, ...],
    bindings: tuple[OperationBinding, ...],
    recommendations: tuple[OperationFeedRecommendation, ...],
) -> None:
    """Validate recommendation IDs, cardinality, and structural references.

    Does not invoke the feeds/speeds calculator. Stale fingerprints remain
    structurally valid.
    """
    definition_by_id = {item.id: item for item in definitions}
    binding_by_id = {item.id: item for item in bindings}
    binding_by_definition = {item.definition_id: item for item in bindings}
    seen_ids: set[str] = set()
    seen_definitions: set[str] = set()
    for item in recommendations:
        if not isinstance(item, OperationFeedRecommendation):
            raise RecommendationError(
                f"unknown recommendation type {type(item)!r}")
        if not item.id:
            raise RecommendationError("recommendation ID must not be empty")
        if item.id in seen_ids:
            raise RecommendationError(f"duplicate recommendation ID {item.id!r}")
        seen_ids.add(item.id)
        if not item.definition_id:
            raise RecommendationError(
                "recommendation definition_id must not be empty")
        if item.definition_id in seen_definitions:
            raise RecommendationError(
                f"definition {item.definition_id!r} already has a "
                f"feed recommendation")
        seen_definitions.add(item.definition_id)
        if item.definition_id not in definition_by_id:
            raise RecommendationError(
                f"unknown definition ID {item.definition_id!r}")
        if not item.binding_id:
            raise RecommendationError(
                "recommendation binding_id must not be empty")
        binding = binding_by_id.get(item.binding_id)
        if binding is None:
            raise RecommendationError(
                f"unknown binding ID {item.binding_id!r}")
        if binding.definition_id != item.definition_id:
            raise RecommendationError(
                f"recommendation {item.id!r} binding {item.binding_id!r} "
                f"belongs to definition {binding.definition_id!r}")
        current = binding_by_definition.get(item.definition_id)
        if current is None or current.id != item.binding_id:
            raise RecommendationError(
                f"recommendation {item.id!r} binding {item.binding_id!r} "
                f"does not match the binding for definition "
                f"{item.definition_id!r}")
        if not item.machine_profile_id:
            raise RecommendationError(
                "recommendation machine_profile_id must not be empty")
        resolve_machine_profile(item.machine_profile_id)
        validate_spindle_rpm(item.spindle_rpm)
        if not item.input_fingerprint:
            raise RecommendationError(
                "recommendation input_fingerprint must not be empty")
        if not isinstance(item.recommendation, FeedRecommendation):
            raise RecommendationError(
                "recommendation payload must be a FeedRecommendation")


def _validate_dimensions(definition: OperationDefinition) -> None:
    if isinstance(definition, ReferenceDefinition):
        return
    validate_positive_distance("target_depth_mm", definition.target_depth_mm)
    if isinstance(definition, ContourDefinition):
        _require_enum("relation", definition.relation, ContourRelation)
        _require_enum("direction", definition.direction, CutDirection)
        validate_nonnegative_optional_distance(
            "stock_allowance_mm", definition.stock_allowance_mm)
    elif isinstance(definition, PocketDefinition):
        _require_enum("direction", definition.direction, CutDirection)
        validate_nonnegative_optional_distance(
            "wall_allowance_mm", definition.wall_allowance_mm)
        validate_nonnegative_optional_distance(
            "floor_allowance_mm", definition.floor_allowance_mm)
    elif isinstance(definition, DrillDefinition):
        validate_nonnegative_optional_distance(
            "retract_height_mm", definition.retract_height_mm)
        validate_optional_positive_distance(
            "peck_depth_mm", definition.peck_depth_mm)
    elif isinstance(definition, SlotDefinition):
        _require_enum("relation", definition.relation, SlotRelation)
        _require_enum("direction", definition.direction, CutDirection)
        validate_optional_positive_distance(
            "slot_width_mm", definition.slot_width_mm)


def _require_enum(name: str, value: object, enum_cls) -> None:
    if not isinstance(value, enum_cls):
        raise OperationDefinitionError(
            f"{name} has unknown value {value!r}")


def _require_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationDefinitionError(
            f"{name} must be a finite number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise OperationDefinitionError(
            f"{name} must be a finite number, got {value!r}")
    return number
