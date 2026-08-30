"""Versioned operation plan aggregating a workspace and definitions (CS-012/CS-013).

An :class:`OperationPlan` is the persistence document for manufacturing
operation definitions and, from v2, tool/material bindings. It embeds a
CS-011 :class:`GeometryWorkspace` rather than extending that workspace, so
the package dependency stays::

    operations → workspace
    operations → feeds_speeds.tools / materials / machines
    operations → feeds_speeds.calculator
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..workspace.errors import WorkspaceError
from ..workspace.models import GeometryWorkspace
from ..workspace.validation import validate_workspace
from .errors import BindingError, OperationDefinitionError, RecommendationError
from .models import (
    OperationBinding,
    OperationDefinition,
    OperationFeedRecommendation,
)
from .validation import (
    validate_operation_bindings,
    validate_operation_definitions,
    validate_operation_recommendations,
)

OPERATION_PLAN_V1 = "camstudio_operation_plan_v1"
OPERATION_PLAN_V2 = "camstudio_operation_plan_v2"
OPERATION_PLAN_V3 = "camstudio_operation_plan_v3"
OPERATION_PLAN_VERSION = OPERATION_PLAN_V3
_SUPPORTED_PLAN_VERSIONS = frozenset({
    OPERATION_PLAN_V1, OPERATION_PLAN_V2, OPERATION_PLAN_V3,
})


@dataclass(frozen=True, slots=True)
class OperationPlan:
    """A versioned workspace plus definitions, bindings, and recommendations."""

    version: str
    workspace: GeometryWorkspace
    definitions: tuple[OperationDefinition, ...] = ()
    bindings: tuple[OperationBinding, ...] = ()
    recommendations: tuple[OperationFeedRecommendation, ...] = ()


def build_operation_plan(
    workspace: GeometryWorkspace,
    definitions: tuple[OperationDefinition, ...] = (),
    bindings: tuple[OperationBinding, ...] = (),
) -> OperationPlan:
    """Wrap ``workspace``, ``definitions``, and ``bindings`` in a validated plan."""
    version = OPERATION_PLAN_VERSION
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

    Rejected while any recommendation or binding still names that
    definition. Remove recommendations, then the binding; there is no
    cascade.
    """
    _resolve_definition(plan, definition_id)
    rec_ids = [
        item.id
        for item in plan.recommendations
        if item.definition_id == definition_id
    ]
    bind_ids = [
        binding.id
        for binding in plan.bindings
        if binding.definition_id == definition_id
    ]
    if rec_ids:
        extra = f" and bindings {bind_ids}" if bind_ids else ""
        raise RecommendationError(
            f"cannot remove definition {definition_id!r}: referenced by "
            f"recommendations {rec_ids}{extra}")
    if bind_ids:
        raise BindingError(
            f"cannot remove definition {definition_id!r}: referenced by "
            f"bindings {bind_ids}")
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
    if plan.version in {OPERATION_PLAN_V1, OPERATION_PLAN_V2} and plan.recommendations:
        raise RecommendationError(
            f"operation-plan {plan.version} cannot carry recommendations; "
            "recommend_feeds_speeds upgrades the document to v3")
    try:
        validate_workspace(plan.workspace)
    except WorkspaceError as exc:
        raise OperationDefinitionError(
            f"operation plan workspace is invalid: {exc}") from exc
    validate_operation_definitions(plan.workspace, plan.definitions)
    validate_operation_bindings(plan.definitions, plan.bindings)
    validate_operation_recommendations(
        plan.definitions, plan.bindings, plan.recommendations)


def _resolve_definition(
    plan: OperationPlan, definition_id: str,
) -> OperationDefinition:
    for definition in plan.definitions:
        if definition.id == definition_id:
            return definition
    raise OperationDefinitionError(
        f"unknown definition ID {definition_id!r}")
