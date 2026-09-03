"""Canonical tool, material, machine, and definition resolution (CS-013/CS-014).

Lookups go through the existing catalogs. Unknown IDs are structural
errors, not advisory feed diagnostics. Catalog objects are not copied
into the binding or recommendation wrapper.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..feeds_speeds.machines import MachineProfile, get_machine
from ..feeds_speeds.materials import Material, get_material
from ..feeds_speeds.tools import Tool, get_tool
from .errors import BindingError, RecommendationError
from .models import (
    OperationBinding,
    OperationDefinition,
    ReferenceDefinition,
)

if TYPE_CHECKING:
    from .plan import OperationPlan


def resolve_tool(binding: OperationBinding) -> Tool:
    """Return the canonical catalog ``Tool`` for ``binding.tool_id``."""
    try:
        return get_tool(binding.tool_id)
    except ValueError as exc:
        raise BindingError(f"unknown tool {binding.tool_id!r}") from exc


def resolve_material(binding: OperationBinding) -> Material:
    """Return the canonical catalog ``Material`` for ``binding.material_id``."""
    try:
        return get_material(binding.material_id)
    except ValueError as exc:
        raise BindingError(f"unknown material {binding.material_id!r}") from exc


def require_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationDefinition:
    """Return the definition named by ``definition_id``, or raise."""
    for definition in plan.definitions:
        if definition.id == definition_id:
            return definition
    raise BindingError(f"unknown definition ID {definition_id!r}")


def resolve_definition(
    plan: OperationPlan, binding: OperationBinding,
) -> OperationDefinition:
    """Return the definition named by ``binding.definition_id``."""
    return require_definition(plan, binding.definition_id)


def require_bindable_definition(definition: OperationDefinition) -> None:
    """Reject ``REFERENCE`` definitions; machining definitions are accepted."""
    if isinstance(definition, ReferenceDefinition):
        raise BindingError(
            f"REFERENCE definition {definition.id!r} cannot be bound")


def binding_for_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationBinding | None:
    """Return the active binding for ``definition_id``, or ``None``."""
    for binding in plan.bindings:
        if binding.definition_id == definition_id:
            return binding
    return None


def validate_spindle_rpm(spindle_rpm: object) -> float:
    """Require a finite requested operating RPM strictly greater than zero."""
    if isinstance(spindle_rpm, bool) or not isinstance(spindle_rpm, (int, float)):
        raise RecommendationError(
            f"spindle_rpm must be a finite number greater than 0, "
            f"got {spindle_rpm!r}")
    number = float(spindle_rpm)
    if not math.isfinite(number) or number <= 0:
        raise RecommendationError(
            f"spindle_rpm must be a finite number greater than 0, "
            f"got {spindle_rpm!r}")
    return number


def resolve_machine_profile(machine_profile_id: str) -> MachineProfile:
    """Return the canonical catalog ``MachineProfile`` for ``machine_profile_id``."""
    try:
        return get_machine(machine_profile_id)
    except ValueError as exc:
        raise RecommendationError(
            f"unknown machine {machine_profile_id!r}") from exc


def require_recommendable_definition(
    definition: OperationDefinition,
) -> None:
    """Reject ``REFERENCE``; machining definitions are accepted."""
    if isinstance(definition, ReferenceDefinition):
        raise RecommendationError(
            f"REFERENCE definition {definition.id!r} cannot receive a "
            f"feed recommendation")


def require_calculator_tool(tool: Tool) -> None:
    """Reject tools the existing calculator cannot process."""
    if tool.flutes is None:
        raise RecommendationError(
            f"tool {tool.id!r} does not provide flute-count input required "
            f"by the feeds/speeds calculator")


@dataclass(frozen=True, slots=True)
class RecommendationInputs:
    """Resolved calculator inputs. Not a persisted planning document."""

    definition: OperationDefinition
    binding: OperationBinding
    tool: Tool
    material: Material
    machine: MachineProfile
    spindle_rpm: float


def resolve_recommendation_inputs(
    plan: OperationPlan,
    definition_id: str,
    machine_profile_id: str,
    spindle_rpm: object,
) -> RecommendationInputs:
    """Resolve definition, binding, catalogs, and requested RPM.

    Does not invoke the feeds/speeds calculator.
    """
    try:
        definition = require_definition(plan, definition_id)
    except BindingError as exc:
        raise RecommendationError(str(exc)) from exc
    require_recommendable_definition(definition)
    binding = binding_for_definition(plan, definition_id)
    if binding is None:
        raise RecommendationError(
            f"definition {definition_id!r} has no tool/material binding")
    try:
        tool = resolve_tool(binding)
        material = resolve_material(binding)
    except BindingError as exc:
        raise RecommendationError(str(exc)) from exc
    require_calculator_tool(tool)
    machine = resolve_machine_profile(machine_profile_id)
    rpm = validate_spindle_rpm(spindle_rpm)
    return RecommendationInputs(
        definition=definition,
        binding=binding,
        tool=tool,
        material=material,
        machine=machine,
        spindle_rpm=rpm,
    )
