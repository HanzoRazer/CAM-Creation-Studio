"""Versioned operation plan aggregating a workspace and definitions (CS-012/CS-013).

An :class:`OperationPlan` is the persistence document for manufacturing
operation definitions and, from v2, tool/material bindings. It embeds a
CS-011 :class:`GeometryWorkspace` rather than extending that workspace, so
the package dependency stays::

    operations → workspace
    operations → feeds_speeds.tools / materials
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..workspace.errors import WorkspaceError
from ..workspace.models import GeometryWorkspace
from ..workspace.validation import validate_workspace
from .errors import BindingError, OperationDefinitionError
from .models import OperationBinding, OperationDefinition
from .validation import (
    validate_operation_bindings,
    validate_operation_definitions,
)

OPERATION_PLAN_V1 = "camstudio_operation_plan_v1"
OPERATION_PLAN_V2 = "camstudio_operation_plan_v2"
# Current write token for newly built plans. Binding mutation always writes v2.
OPERATION_PLAN_VERSION = OPERATION_PLAN_V1
_SUPPORTED_PLAN_VERSIONS = frozenset({OPERATION_PLAN_V1, OPERATION_PLAN_V2})


@dataclass(frozen=True, slots=True)
class OperationPlan:
    """A versioned workspace plus definitions and optional bindings."""

    version: str
    workspace: GeometryWorkspace
    definitions: tuple[OperationDefinition, ...] = ()
    bindings: tuple[OperationBinding, ...] = ()


def build_operation_plan(
    workspace: GeometryWorkspace,
    definitions: tuple[OperationDefinition, ...] = (),
    bindings: tuple[OperationBinding, ...] = (),
) -> OperationPlan:
    """Wrap ``workspace``, ``definitions``, and ``bindings`` in a validated plan."""
    version = OPERATION_PLAN_V2 if bindings else OPERATION_PLAN_VERSION
    plan = OperationPlan(
        version=version,
        workspace=workspace,
        definitions=tuple(definitions),
        bindings=tuple(bindings),
    )
    validate_operation_plan(plan)
    return plan


def add_definition(
    plan: OperationPlan, definition: OperationDefinition,
) -> OperationPlan:
    """Append ``definition``. Rejected when the intent is already owned."""
    updated = replace(plan, definitions=plan.definitions + (definition,))
    validate_operation_plan(updated)
    return updated


def replace_definition(
    plan: OperationPlan,
    definition_id: str,
    replacement: OperationDefinition,
) -> OperationPlan:
    """Replace one definition. The stored ID is ``definition_id``.

    Changing ``intent_id`` to one already owned by another definition is
    rejected. The one-definition-per-intent rule is applied after the
    mutation, not only at initial construction. Bindings survive when the
    definition ID is unchanged.
    """
    _resolve_definition(plan, definition_id)
    stored = replace(replacement, id=definition_id)
    definitions = tuple(
        stored if item.id == definition_id else item
        for item in plan.definitions
    )
    updated = replace(plan, definitions=definitions)
    validate_operation_plan(updated)
    return updated


def remove_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationPlan:
    """Remove one definition by ID.

    Rejected while any binding still names that definition. Remove the
    binding first; there is no cascade.
    """
    _resolve_definition(plan, definition_id)
    dependents = [
        binding.id
        for binding in plan.bindings
        if binding.definition_id == definition_id
    ]
    if dependents:
        raise BindingError(
            f"cannot remove definition {definition_id!r}: referenced by "
            f"bindings {dependents}")
    definitions = tuple(
        item for item in plan.definitions if item.id != definition_id)
    updated = replace(plan, definitions=definitions)
    validate_operation_plan(updated)
    return updated


def validate_operation_plan(plan: OperationPlan) -> None:
    """Raise if the plan version, workspace, definitions, or bindings are invalid."""
    if plan.version not in _SUPPORTED_PLAN_VERSIONS:
        raise OperationDefinitionError(
            f"unknown operation-plan version {plan.version!r}; "
            f"expected one of {sorted(_SUPPORTED_PLAN_VERSIONS)}")
    if plan.version == OPERATION_PLAN_V1 and plan.bindings:
        raise BindingError(
            "operation-plan v1 cannot carry bindings; bind_operation "
            "upgrades the document to v2")
    try:
        validate_workspace(plan.workspace)
    except WorkspaceError as exc:
        raise OperationDefinitionError(
            f"operation plan workspace is invalid: {exc}") from exc
    validate_operation_definitions(plan.workspace, plan.definitions)
    validate_operation_bindings(plan.definitions, plan.bindings)


def _resolve_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationDefinition:
    for definition in plan.definitions:
        if definition.id == definition_id:
            return definition
    raise OperationDefinitionError(
        f"unknown definition ID {definition_id!r}")
