"""OperationPlan is the CS-012 persistence aggregate."""

from __future__ import annotations

import dataclasses

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.builder import (
    define_contour,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.errors import OperationDefinitionError
from cam_creation_studio.operations.models import ContourDefinition
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_VERSION,
    OperationPlan,
    add_definition,
    build_operation_plan,
    remove_definition,
    replace_definition,
    validate_operation_plan,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import (
    assign_operation,
    remove_operation,
)
from cam_creation_studio.workspace.selections import create_selection


def _workspace_with(*kinds: OperationKind):
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    for kind in kinds:
        workspace = assign_operation(
            workspace, kind.value, kind, "sel-1", id=f"op-{kind.value}")
    return workspace


def test_build_operation_plan_defaults_to_empty_definitions():
    workspace = _workspace_with()
    plan = build_operation_plan(workspace)
    assert plan.version == OPERATION_PLAN_VERSION
    assert plan.workspace is workspace
    assert plan.definitions == ()
    assert plan.bindings == ()
    assert plan.__dataclass_params__.frozen is True


def test_add_definition_appends_without_mutating_the_builder_result():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = build_operation_plan(workspace)
    updated = add_definition(plan, definition)
    assert plan.definitions == ()
    assert updated.definitions == (definition,)
    assert definition.id == "d1"


def test_add_definition_rejects_a_second_owner_of_the_same_intent():
    workspace = _workspace_with(OperationKind.CONTOUR)
    first = define_contour(workspace, "op-contour", 6.0, id="d1")
    second = define_contour(
        workspace, "op-contour", 3.0, id="d2", existing_count=1)
    plan = add_definition(build_operation_plan(workspace), first)
    with pytest.raises(OperationDefinitionError, match="already has a definition"):
        add_definition(plan, second)


def test_replace_definition_preserves_id():
    workspace = _workspace_with(OperationKind.CONTOUR)
    original = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = add_definition(build_operation_plan(workspace), original)
    replacement = define_contour(
        workspace, "op-contour", 8.0, id="ignored", existing_count=1)
    updated = replace_definition(plan, "d1", replacement)
    assert updated.definitions[0].id == "d1"
    assert updated.definitions[0].target_depth_mm == 8.0


def test_replace_definition_cannot_steal_another_intent():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    plan = build_operation_plan(workspace, (contour, pocket))
    stolen = define_pocket(workspace, "op-pocket", 5.0, id="d1")
    with pytest.raises(OperationDefinitionError, match="already has a definition"):
        replace_definition(plan, "d1", stolen)


def test_replace_definition_may_retarget_a_free_matching_intent():
    workspace = _workspace_with(OperationKind.CONTOUR)
    workspace = assign_operation(
        workspace, "inner", OperationKind.CONTOUR, "sel-1", id="op-inner")
    original = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = add_definition(build_operation_plan(workspace), original)
    retargeted = define_contour(workspace, "op-inner", 2.0, id="other")
    updated = replace_definition(plan, "d1", retargeted)
    assert updated.definitions[0].id == "d1"
    assert updated.definitions[0].intent_id == "op-inner"
    assert updated.definitions[0].target_depth_mm == 2.0


def test_remove_definition_then_intent_is_the_supported_lifecycle():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = add_definition(build_operation_plan(workspace), definition)
    cleared = remove_definition(plan, "d1")
    assert cleared.definitions == ()
    updated_workspace = remove_operation(cleared.workspace, "op-contour")
    rebuilt = build_operation_plan(updated_workspace, cleared.definitions)
    assert rebuilt.definitions == ()
    assert rebuilt.workspace.operations == ()


def test_workspace_may_drop_an_intent_the_plan_still_names():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = add_definition(build_operation_plan(workspace), definition)
    dangling_workspace = remove_operation(plan.workspace, "op-contour")
    with pytest.raises(OperationDefinitionError, match="unknown operation intent"):
        build_operation_plan(dangling_workspace, plan.definitions)


def test_unknown_definition_id_is_rejected():
    plan = build_operation_plan(_workspace_with())
    with pytest.raises(OperationDefinitionError, match="unknown definition ID"):
        remove_definition(plan, "missing")
    replacement = ContourDefinition(
        id="x", intent_id="op-contour", target_depth_mm=1.0)
    with pytest.raises(OperationDefinitionError, match="unknown definition ID"):
        replace_definition(plan, "missing", replacement)


def test_unknown_plan_version_is_rejected():
    workspace = _workspace_with()
    plan = OperationPlan(
        version="camstudio_operation_plan_v0", workspace=workspace)
    with pytest.raises(OperationDefinitionError, match="unknown operation-plan version"):
        validate_operation_plan(plan)


def test_reference_definition_joins_a_plan():
    workspace = _workspace_with(OperationKind.REFERENCE)
    definition = define_reference(workspace, "op-reference", id="d1")
    plan = add_definition(build_operation_plan(workspace), definition)
    assert plan.definitions[0] is definition


def test_plan_is_frozen():
    plan = build_operation_plan(_workspace_with())
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.definitions = ()  # type: ignore[misc]
