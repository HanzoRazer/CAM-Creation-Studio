"""Versioned JSON for an operation plan (CS-012).

The document is an operation plan, not a bare geometry workspace. A CS-011
workspace document is embedded under ``workspace`` and remains independently
valid. Unknown versions, discriminators, and enum values fail closed.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..workspace.errors import WorkspaceError
from ..workspace.models import WORKSPACE_VERSION
from ..workspace.serialization import workspace_from_dict, workspace_to_dict
from .enums import ContourRelation, CutDirection, SlotRelation
from .errors import BindingError, OperationDefinitionError
from .models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationBinding,
    OperationDefinition,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
    definition_type_name,
)
from .plan import (
    OPERATION_PLAN_V1,
    OPERATION_PLAN_V2,
    OPERATION_PLAN_VERSION,
    OperationPlan,
    validate_operation_plan,
)
from .validation import (
    validate_nonnegative_optional_distance,
    validate_optional_positive_distance,
    validate_positive_distance,
)

_DEFINITION_FROM_TYPE: dict[str, Callable[[dict], OperationDefinition]] = {}


def operation_definition_to_dict(definition: OperationDefinition) -> dict:
    """JSON-ready definition with an explicit ``definition_type`` discriminator."""
    payload: dict = {
        "definition_type": definition_type_name(definition),
        "id": definition.id,
        "intent_id": definition.intent_id,
    }
    if isinstance(definition, ReferenceDefinition):
        return payload
    payload["target_depth_mm"] = definition.target_depth_mm
    if isinstance(definition, ContourDefinition):
        payload["relation"] = definition.relation.value
        payload["direction"] = definition.direction.value
        payload["stock_allowance_mm"] = definition.stock_allowance_mm
    elif isinstance(definition, PocketDefinition):
        payload["direction"] = definition.direction.value
        payload["wall_allowance_mm"] = definition.wall_allowance_mm
        payload["floor_allowance_mm"] = definition.floor_allowance_mm
    elif isinstance(definition, DrillDefinition):
        payload["retract_height_mm"] = definition.retract_height_mm
        payload["peck_depth_mm"] = definition.peck_depth_mm
    elif isinstance(definition, SlotDefinition):
        payload["relation"] = definition.relation.value
        payload["direction"] = definition.direction.value
        payload["slot_width_mm"] = definition.slot_width_mm
    return payload


def operation_definition_from_dict(data: object) -> OperationDefinition:
    """Rebuild one definition. Unknown discriminators and enums fail closed."""
    raw = _expect_object(data, "operation definition")
    definition_type = _field(raw, "definition_type", "operation definition")
    loader = _DEFINITION_FROM_TYPE.get(definition_type)
    if loader is None:
        raise OperationDefinitionError(
            f"unknown definition type {definition_type!r}")
    return loader(raw)


def operation_binding_to_dict(binding: OperationBinding) -> dict:
    """JSON-ready binding. Catalog IDs only."""
    return {
        "id": binding.id,
        "definition_id": binding.definition_id,
        "tool_id": binding.tool_id,
        "material_id": binding.material_id,
    }


def operation_binding_from_dict(data: object) -> OperationBinding:
    """Rebuild one binding. Catalog membership is checked at plan validation."""
    raw = _expect_object(data, "operation binding")
    field = "operation binding"
    binding_id = _field(raw, "id", field)
    definition_id = _field(raw, "definition_id", field)
    tool_id = _field(raw, "tool_id", field)
    material_id = _field(raw, "material_id", field)
    if not binding_id:
        raise BindingError("binding ID must not be empty")
    if not definition_id:
        raise BindingError("binding definition_id must not be empty")
    if not tool_id:
        raise BindingError("tool_id must not be empty")
    if not material_id:
        raise BindingError("material_id must not be empty")
    return OperationBinding(
        id=binding_id,
        definition_id=definition_id,
        tool_id=tool_id,
        material_id=material_id,
    )


def operation_plan_to_dict(plan: OperationPlan) -> dict:
    """JSON-ready plan. v1 omits bindings; v2 includes them."""
    payload = {
        "version": plan.version,
        "workspace": workspace_to_dict(plan.workspace),
        "definitions": [
            operation_definition_to_dict(definition)
            for definition in plan.definitions
        ],
    }
    if plan.version == OPERATION_PLAN_V1:
        return payload
    payload["bindings"] = [
        operation_binding_to_dict(binding) for binding in plan.bindings
    ]
    return payload


def operation_plan_from_dict(data: object) -> OperationPlan:
    """Rebuild a plan and structurally validate it."""
    if not isinstance(data, dict):
        raise OperationDefinitionError("operation plan document must be an object")
    if "version" not in data:
        raise OperationDefinitionError(
            "not an operation plan document: missing version "
            f"{OPERATION_PLAN_VERSION!r}")
    version = data["version"]
    if version not in (OPERATION_PLAN_V1, OPERATION_PLAN_V2):
        if version == WORKSPACE_VERSION:
            raise OperationDefinitionError(
                "not an operation plan document: "
                f"got geometry workspace version {version!r}")
        raise OperationDefinitionError(
            f"unknown operation-plan version {version!r}; "
            f"expected {OPERATION_PLAN_V1!r} or {OPERATION_PLAN_V2!r}")

    raw_workspace = data.get("workspace")
    try:
        workspace = workspace_from_dict(raw_workspace)
    except WorkspaceError as exc:
        raise OperationDefinitionError(
            f"malformed nested workspace: {exc}") from exc

    definitions = tuple(
        operation_definition_from_dict(item)
        for item in _expect_list(data.get("definitions", []), "definitions")
    )
    if version == OPERATION_PLAN_V1:
        extra = data.get("bindings")
        if extra:
            raise BindingError(
                "operation-plan v1 cannot carry bindings; bind_operation "
                "upgrades the document to v2")
        bindings: tuple[OperationBinding, ...] = ()
    else:
        bindings = tuple(
            operation_binding_from_dict(item)
            for item in _expect_list(data.get("bindings", []), "bindings")
        )
    plan = OperationPlan(
        version=version,
        workspace=workspace,
        definitions=definitions,
        bindings=bindings,
    )
    validate_operation_plan(plan)
    return plan


def operation_plan_to_json(
    plan: OperationPlan,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """Deterministic JSON: no wall-clock fields; keys sorted by default."""
    return json.dumps(
        operation_plan_to_dict(plan), indent=indent, sort_keys=sort_keys)


def operation_plan_from_json(text: str) -> OperationPlan:
    """Parse JSON and rebuild a validated plan."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OperationDefinitionError(
            f"malformed operation-plan JSON: {exc}") from exc
    return operation_plan_from_dict(data)


def _expect_object(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise OperationDefinitionError(f"malformed {field}")
    return value


def _expect_list(value: object, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OperationDefinitionError(f"{field} must be a list")
    return value


def _field(item: dict, name: str, field: str):
    if name not in item:
        raise OperationDefinitionError(f"{field} is missing {name!r}")
    return item[name]


def _identity(raw: dict) -> tuple[str, str]:
    field = "operation definition"
    identity = _field(raw, "id", field), _field(raw, "intent_id", field)
    if not identity[0]:
        raise OperationDefinitionError("definition ID must not be empty")
    if not identity[1]:
        raise OperationDefinitionError("intent_id must not be empty")
    return identity


def _enum(enum_cls, value, label: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise OperationDefinitionError(f"unknown {label} {value!r}") from exc


def _contour(raw: dict) -> ContourDefinition:
    definition_id, intent_id = _identity(raw)
    return ContourDefinition(
        id=definition_id,
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", _field(raw, "target_depth_mm", "contour")),
        relation=_enum(
            ContourRelation, raw.get("relation", ContourRelation.ON.value),
            "contour relation"),
        direction=_enum(
            CutDirection, raw.get("direction", CutDirection.UNSPECIFIED.value),
            "cut direction"),
        stock_allowance_mm=validate_nonnegative_optional_distance(
            "stock_allowance_mm", raw.get("stock_allowance_mm")),
    )


def _pocket(raw: dict) -> PocketDefinition:
    definition_id, intent_id = _identity(raw)
    return PocketDefinition(
        id=definition_id,
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", _field(raw, "target_depth_mm", "pocket")),
        direction=_enum(
            CutDirection, raw.get("direction", CutDirection.UNSPECIFIED.value),
            "cut direction"),
        wall_allowance_mm=validate_nonnegative_optional_distance(
            "wall_allowance_mm", raw.get("wall_allowance_mm")),
        floor_allowance_mm=validate_nonnegative_optional_distance(
            "floor_allowance_mm", raw.get("floor_allowance_mm")),
    )


def _drill(raw: dict) -> DrillDefinition:
    definition_id, intent_id = _identity(raw)
    return DrillDefinition(
        id=definition_id,
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", _field(raw, "target_depth_mm", "drill")),
        retract_height_mm=validate_nonnegative_optional_distance(
            "retract_height_mm", raw.get("retract_height_mm")),
        peck_depth_mm=validate_optional_positive_distance(
            "peck_depth_mm", raw.get("peck_depth_mm")),
    )


def _engrave(raw: dict) -> EngraveDefinition:
    definition_id, intent_id = _identity(raw)
    return EngraveDefinition(
        id=definition_id,
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", _field(raw, "target_depth_mm", "engrave")),
    )


def _slot(raw: dict) -> SlotDefinition:
    definition_id, intent_id = _identity(raw)
    return SlotDefinition(
        id=definition_id,
        intent_id=intent_id,
        target_depth_mm=validate_positive_distance(
            "target_depth_mm", _field(raw, "target_depth_mm", "slot")),
        relation=_enum(
            SlotRelation, raw.get("relation", SlotRelation.ON_PATH.value),
            "slot relation"),
        direction=_enum(
            CutDirection, raw.get("direction", CutDirection.UNSPECIFIED.value),
            "cut direction"),
        slot_width_mm=validate_optional_positive_distance(
            "slot_width_mm", raw.get("slot_width_mm")),
    )


def _reference(raw: dict) -> ReferenceDefinition:
    definition_id, intent_id = _identity(raw)
    return ReferenceDefinition(id=definition_id, intent_id=intent_id)


_DEFINITION_FROM_TYPE.update({
    "contour": _contour,
    "pocket": _pocket,
    "drill": _drill,
    "engrave": _engrave,
    "slot": _slot,
    "reference": _reference,
})
