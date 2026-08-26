"""Tool and material binding lifecycle on an operation plan (CS-013)."""

from __future__ import annotations

import pytest

from cam_creation_studio.feeds_speeds.materials import list_materials
from cam_creation_studio.feeds_speeds.tools import get_tool
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import (
    bind_operation,
    remove_binding,
    replace_binding,
)
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_engrave,
    define_pocket,
    define_reference,
)
from cam_creation_studio.operations.errors import BindingError
from cam_creation_studio.operations.ids import make_binding_id
from cam_creation_studio.operations.plan import (
    OPERATION_PLAN_V1,
    OPERATION_PLAN_V2,
    add_definition,
    build_operation_plan,
    remove_definition,
    replace_definition,
)
from cam_creation_studio.operations.resolution import (
    binding_for_definition,
    resolve_material,
    resolve_tool,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
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


def _contour_plan():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    return build_operation_plan(workspace, (definition,))


def test_bind_operation_records_catalog_ids():
    plan = bind_operation(
        _contour_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    binding = plan.bindings[0]
    assert binding.id == "b1"
    assert binding.definition_id == "d1"
    assert binding.tool_id == "endmill_1_4"
    assert binding.material_id == "hardwood"
    assert plan.version == OPERATION_PLAN_V2
    assert resolve_tool(binding) is get_tool("endmill_1_4")


def test_generated_binding_id_is_deterministic():
    plan = _contour_plan()
    first = bind_operation(plan, "d1", "endmill_1_4", "hardwood")
    again = bind_operation(plan, "d1", "endmill_1_4", "hardwood")
    expected = make_binding_id(
        "d1", "endmill_1_4", "hardwood", existing_count=0)
    assert first.bindings[0].id == expected
    assert again.bindings[0].id == first.bindings[0].id


def test_second_bind_on_the_same_definition_is_rejected():
    plan = bind_operation(_contour_plan(), "d1", "endmill_1_4", "hardwood")
    with pytest.raises(BindingError, match="already has a binding"):
        bind_operation(plan, "d1", "endmill_1_8", "mdf")


def test_replace_binding_preserves_id_and_definition():
    plan = bind_operation(
        _contour_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    updated = replace_binding(plan, "b1", "engraver", "acrylic")
    assert updated.bindings[0].id == "b1"
    assert updated.bindings[0].definition_id == "d1"
    assert updated.bindings[0].tool_id == "engraver"
    assert updated.bindings[0].material_id == "acrylic"
    assert binding_for_definition(updated, "d1") is updated.bindings[0]


def test_remove_binding_leaves_definition_in_place():
    plan = bind_operation(
        _contour_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    cleared = remove_binding(plan, "b1")
    assert cleared.bindings == ()
    assert cleared.definitions[0].id == "d1"
    assert cleared.workspace is plan.workspace


def test_remove_definition_rejected_while_bound():
    plan = bind_operation(
        _contour_plan(), "d1", "endmill_1_4", "hardwood", id="b1")
    with pytest.raises(BindingError, match="referenced by bindings"):
        remove_definition(plan, "d1")
    cleared = remove_binding(plan, "b1")
    removed = remove_definition(cleared, "d1")
    assert removed.definitions == ()
    assert removed.bindings == ()


def test_replace_definition_keeps_binding_when_id_is_unchanged():
    workspace = _workspace_with(OperationKind.CONTOUR)
    original = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (original,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    deeper = define_contour(workspace, "op-contour", 8.0, id="ignored")
    updated = replace_definition(plan, "d1", deeper)
    assert updated.definitions[0].target_depth_mm == 8.0
    assert updated.bindings[0].id == "b1"
    assert updated.bindings[0].definition_id == "d1"


def test_unknown_definition_tool_and_material_are_rejected():
    plan = _contour_plan()
    with pytest.raises(BindingError, match="unknown definition ID"):
        bind_operation(plan, "missing", "endmill_1_4", "hardwood")
    with pytest.raises(BindingError, match="unknown tool"):
        bind_operation(plan, "d1", "missing-tool", "hardwood")
    with pytest.raises(BindingError, match="unknown material"):
        bind_operation(plan, "d1", "endmill_1_4", "missing-material")


def test_reference_definition_cannot_be_bound():
    workspace = _workspace_with(OperationKind.REFERENCE)
    definition = define_reference(workspace, "op-reference", id="d-ref")
    plan = build_operation_plan(workspace, (definition,))
    with pytest.raises(BindingError, match="REFERENCE"):
        bind_operation(plan, "d-ref", "endmill_1_4", "hardwood")


def test_drill_with_endmill_and_hardwood_is_structurally_valid():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = define_drill(workspace, "op-drill", 10.0, id="d-drill")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d-drill", "endmill_1_4", "hardwood", id="b1")
    assert plan.bindings[0].tool_id == "endmill_1_4"


def test_engrave_with_ballnose_and_stainless_is_structurally_valid():
    workspace = _workspace_with(OperationKind.ENGRAVE)
    definition = define_engrave(workspace, "op-engrave", 0.2, id="d-engrave")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d-engrave", "ballnose", "stainless", id="b1")
    assert resolve_material(plan.bindings[0]).id == "stainless"


def test_every_catalogued_material_is_bindable():
    plan = _contour_plan()
    bound = bind_operation(plan, "d1", "endmill_1_8", "softwood", id="b1")
    for material in list_materials():
        bound = replace_binding(bound, "b1", "endmill_1_8", material.id)
        assert bound.bindings[0].material_id == material.id


def test_unbound_definitions_remain_valid():
    workspace = _workspace_with(
        OperationKind.CONTOUR, OperationKind.POCKET, OperationKind.DRILL)
    contour = define_contour(workspace, "op-contour", 6.0, id="d1")
    pocket = define_pocket(workspace, "op-pocket", 4.0, id="d2")
    drill = define_drill(workspace, "op-drill", 8.0, id="d3")
    plan = build_operation_plan(workspace, (contour, pocket, drill))
    bound = bind_operation(plan, "d1", "endmill_1_4", "mdf", id="b1")
    assert len(bound.definitions) == 3
    assert len(bound.bindings) == 1
    assert binding_for_definition(bound, "d2") is None


def test_bind_operation_upgrades_a_v1_plan():
    plan = _contour_plan()
    assert plan.version == OPERATION_PLAN_V1
    updated = bind_operation(plan, "d1", "endmill_1_4", "hardwood")
    assert updated.version == OPERATION_PLAN_V2
    assert plan.version == OPERATION_PLAN_V1
    assert plan.bindings == ()


def test_unknown_binding_id_is_rejected():
    plan = _contour_plan()
    with pytest.raises(BindingError, match="unknown binding ID"):
        remove_binding(plan, "missing")
    with pytest.raises(BindingError, match="unknown binding ID"):
        replace_binding(plan, "missing", "endmill_1_4", "hardwood")


def test_two_definitions_may_each_have_a_binding():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.POCKET)
    plan = add_definition(
        build_operation_plan(
            workspace, (define_contour(workspace, "op-contour", 6.0, id="d1"),)),
        define_pocket(workspace, "op-pocket", 4.0, id="d2"))
    plan = bind_operation(plan, "d1", "endmill_1_4", "hardwood", id="b1")
    plan = bind_operation(plan, "d2", "endmill_1_8", "mdf", id="b2")
    assert [item.definition_id for item in plan.bindings] == ["d1", "d2"]
