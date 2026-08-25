"""Versioned operation plan aggregating a workspace and definitions (CS-012).

An :class:`OperationPlan` is the persistence document for manufacturing
operation definitions. It embeds a CS-011 :class:`GeometryWorkspace` rather
than extending that workspace, so the package dependency stays::

    operations → workspace

Definitions are not stored on :class:`GeometryWorkspace`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..workspace.errors import WorkspaceError
from ..workspace.models import GeometryWorkspace
from ..workspace.validation import validate_workspace
from .errors import OperationDefinitionError
from .models import OperationDefinition
from .validation import validate_operation_definitions

OPERATION_PLAN_VERSION = "camstudio_operation_plan_v1"


@dataclass(frozen=True, slots=True)
class OperationPlan:
    """A versioned workspace plus its manufacturing operation definitions."""

    version: str
    workspace: GeometryWorkspace
    definitions: tuple[OperationDefinition, ...] = ()


def build_operation_plan(
    workspace: GeometryWorkspace,
    definitions: tuple[OperationDefinition, ...] = (),
) -> OperationPlan:
    """Wrap ``workspace`` and ``definitions`` in a validated plan."""
    plan = OperationPlan(
        version=OPERATION_PLAN_VERSION,
        workspace=workspace,
        definitions=tuple(definitions),
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
    mutation, not only at initial construction.
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
    """Remove one definition by ID."""
    _resolve_definition(plan, definition_id)
    definitions = tuple(
        item for item in plan.definitions if item.id != definition_id)
    updated = replace(plan, definitions=definitions)
    validate_operation_plan(updated)
    return updated


def validate_operation_plan(plan: OperationPlan) -> None:
    """Raise if the plan version, workspace, or definitions are invalid."""
    if plan.version != OPERATION_PLAN_VERSION:
        raise OperationDefinitionError(
            f"unknown operation-plan version {plan.version!r}; "
            f"expected {OPERATION_PLAN_VERSION!r}")
    try:
        validate_workspace(plan.workspace)
    except WorkspaceError as exc:
        raise OperationDefinitionError(
            f"operation plan workspace is invalid: {exc}") from exc
    validate_operation_definitions(plan.workspace, plan.definitions)


def _resolve_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationDefinition:
    for definition in plan.definitions:
        if definition.id == definition_id:
            return definition
    raise OperationDefinitionError(
        f"unknown definition ID {definition_id!r}")
