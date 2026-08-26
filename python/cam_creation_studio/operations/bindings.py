"""Bind, replace, and remove tool/material bindings on an operation plan."""

from __future__ import annotations

from dataclasses import replace

from .errors import BindingError
from .ids import make_binding_id
from .models import OperationBinding
from .plan import OPERATION_PLAN_V2, OperationPlan, validate_operation_plan
from .resolution import (
    binding_for_definition,
    require_bindable_definition,
    require_definition,
    resolve_material,
    resolve_tool,
)


def bind_operation(
    plan: OperationPlan,
    definition_id: str,
    tool_id: str,
    material_id: str,
    *,
    id: str | None = None,
) -> OperationPlan:
    """Attach one tool/material pair to ``definition_id``.

    Rejected when the definition already has a binding; use
    :func:`replace_binding` to change an existing pair. The returned plan
    is version v2.
    """
    definition = require_definition(plan, definition_id)
    require_bindable_definition(definition)
    existing = binding_for_definition(plan, definition_id)
    if existing is not None:
        raise BindingError(
            f"definition {definition_id!r} already has a binding "
            f"{existing.id!r}")
    binding_id = id if id is not None else make_binding_id(
        definition_id, tool_id, material_id,
        existing_count=len(plan.bindings),
    )
    if not binding_id:
        raise BindingError("binding ID must not be empty")
    binding = OperationBinding(
        id=binding_id,
        definition_id=definition_id,
        tool_id=tool_id,
        material_id=material_id,
    )
    resolve_tool(binding)
    resolve_material(binding)
    updated = replace(
        plan,
        version=OPERATION_PLAN_V2,
        bindings=plan.bindings + (binding,),
    )
    validate_operation_plan(updated)
    return updated


def replace_binding(
    plan: OperationPlan,
    binding_id: str,
    tool_id: str,
    material_id: str,
) -> OperationPlan:
    """Replace tool and material for one binding. ID and definition stay put."""
    current = _resolve_binding(plan, binding_id)
    stored = OperationBinding(
        id=binding_id,
        definition_id=current.definition_id,
        tool_id=tool_id,
        material_id=material_id,
    )
    resolve_tool(stored)
    resolve_material(stored)
    bindings = tuple(
        stored if item.id == binding_id else item
        for item in plan.bindings
    )
    updated = replace(plan, version=OPERATION_PLAN_V2, bindings=bindings)
    validate_operation_plan(updated)
    return updated


def remove_binding(
    plan: OperationPlan, binding_id: str,
) -> OperationPlan:
    """Remove one binding. The definition remains."""
    _resolve_binding(plan, binding_id)
    bindings = tuple(
        item for item in plan.bindings if item.id != binding_id)
    updated = replace(plan, bindings=bindings)
    validate_operation_plan(updated)
    return updated


def _resolve_binding(
    plan: OperationPlan, binding_id: str,
) -> OperationBinding:
    for binding in plan.bindings:
        if binding.id == binding_id:
            return binding
    raise BindingError(f"unknown binding ID {binding_id!r}")
