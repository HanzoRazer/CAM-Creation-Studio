"""Canonical tool, material, and definition resolution (CS-013).

Lookups go through the existing catalogs. Unknown IDs are structural
:class:`BindingError`s, not advisory feed diagnostics. Catalog objects are
not copied into the binding.
"""

from __future__ import annotations

from ..feeds_speeds.materials import Material, get_material
from ..feeds_speeds.tools import Tool, get_tool
from .errors import BindingError
from .models import (
    OperationBinding,
    OperationDefinition,
    ReferenceDefinition,
)
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
