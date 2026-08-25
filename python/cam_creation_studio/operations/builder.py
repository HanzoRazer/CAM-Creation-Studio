"""Operation-specific constructors (CS-012).

Builders resolve a CS-011 intent, require the matching operation kind,
validate dimensional fields, and return an immutable definition. They do
not mutate an :class:`~cam_creation_studio.operations.plan.OperationPlan`.
"""

from __future__ import annotations

from ..workspace.models import GeometryWorkspace, OperationKind
from .enums import ContourRelation, CutDirection, SlotRelation
from .errors import OperationDefinitionError
from .ids import make_operation_definition_id
from .models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
)
from .validation import (
    require_intent_kind,
    resolve_intent,
    validate_nonnegative_optional_distance,
    validate_operation_definition,
    validate_optional_positive_distance,
    validate_positive_distance,
)


def define_contour(
    workspace: GeometryWorkspace,
    intent_id: str,
    target_depth_mm: float,
    *,
    relation: ContourRelation | str = ContourRelation.ON,
    direction: CutDirection | str = CutDirection.UNSPECIFIED,
    stock_allowance_mm: float | None = None,
    id: str | None = None,
    existing_count: int = 0,
) -> ContourDefinition:
    """Build a contour definition for ``intent_id``. No offset is computed."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.CONTOUR)
    definition = ContourDefinition(
        id=_definition_id("contour", intent_id, id, existing_count),
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", target_depth_mm),
        relation=_coerce_enum(ContourRelation, relation, "contour relation"),
        direction=_coerce_enum(CutDirection, direction, "cut direction"),
        stock_allowance_mm=validate_nonnegative_optional_distance(
            "stock_allowance_mm", stock_allowance_mm),
    )
    validate_operation_definition(workspace, definition)
    return definition


def define_pocket(
    workspace: GeometryWorkspace,
    intent_id: str,
    target_depth_mm: float,
    *,
    direction: CutDirection | str = CutDirection.UNSPECIFIED,
    wall_allowance_mm: float | None = None,
    floor_allowance_mm: float | None = None,
    id: str | None = None,
    existing_count: int = 0,
) -> PocketDefinition:
    """Build a pocket definition. No clearing algorithm is invoked."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.POCKET)
    definition = PocketDefinition(
        id=_definition_id("pocket", intent_id, id, existing_count),
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", target_depth_mm),
        direction=_coerce_enum(CutDirection, direction, "cut direction"),
        wall_allowance_mm=validate_nonnegative_optional_distance(
            "wall_allowance_mm", wall_allowance_mm),
        floor_allowance_mm=validate_nonnegative_optional_distance(
            "floor_allowance_mm", floor_allowance_mm),
    )
    validate_operation_definition(workspace, definition)
    return definition


def define_drill(
    workspace: GeometryWorkspace,
    intent_id: str,
    target_depth_mm: float,
    *,
    retract_height_mm: float | None = None,
    peck_depth_mm: float | None = None,
    id: str | None = None,
    existing_count: int = 0,
) -> DrillDefinition:
    """Build a drill definition. No canned cycle is generated."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.DRILL)
    definition = DrillDefinition(
        id=_definition_id("drill", intent_id, id, existing_count),
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", target_depth_mm),
        retract_height_mm=validate_nonnegative_optional_distance(
            "retract_height_mm", retract_height_mm),
        peck_depth_mm=validate_optional_positive_distance(
            "peck_depth_mm", peck_depth_mm),
    )
    validate_operation_definition(workspace, definition)
    return definition


def define_engrave(
    workspace: GeometryWorkspace,
    intent_id: str,
    target_depth_mm: float,
    *,
    id: str | None = None,
    existing_count: int = 0,
) -> EngraveDefinition:
    """Build an engrave definition. v1 is depth only."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.ENGRAVE)
    definition = EngraveDefinition(
        id=_definition_id("engrave", intent_id, id, existing_count),
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", target_depth_mm),
    )
    validate_operation_definition(workspace, definition)
    return definition


def define_slot(
    workspace: GeometryWorkspace,
    intent_id: str,
    target_depth_mm: float,
    *,
    relation: SlotRelation | str = SlotRelation.ON_PATH,
    slot_width_mm: float | None = None,
    direction: CutDirection | str = CutDirection.UNSPECIFIED,
    id: str | None = None,
    existing_count: int = 0,
) -> SlotDefinition:
    """Build a slot definition. Width is finished-size intent, not a cutter."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.SLOT)
    definition = SlotDefinition(
        id=_definition_id("slot", intent_id, id, existing_count),
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", target_depth_mm),
        slot_width_mm=validate_optional_positive_distance(
            "slot_width_mm", slot_width_mm),
        direction=_coerce_enum(CutDirection, direction, "cut direction"),
        relation=_coerce_enum(SlotRelation, relation, "slot relation"),
    )
    validate_operation_definition(workspace, definition)
    return definition


def define_reference(
    workspace: GeometryWorkspace,
    intent_id: str,
    *,
    id: str | None = None,
    existing_count: int = 0,
) -> ReferenceDefinition:
    """Build a non-machining reference definition. No depth is accepted."""
    intent = resolve_intent(workspace, intent_id)
    require_intent_kind(intent, OperationKind.REFERENCE)
    definition = ReferenceDefinition(
        id=_definition_id("reference", intent_id, id, existing_count),
        intent_id=intent_id,
    )
    validate_operation_definition(workspace, definition)
    return definition


def _definition_id(
    definition_type: str,
    intent_id: str,
    supplied: str | None,
    existing_count: int,
) -> str:
    if supplied is not None:
        if not supplied:
            raise OperationDefinitionError("definition ID must not be empty")
        return supplied
    return make_operation_definition_id(
        definition_type, intent_id, existing_count=existing_count)


def _coerce_enum(enum_cls, value, label: str):
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise OperationDefinitionError(
            f"unknown {label} {value!r}") from exc
