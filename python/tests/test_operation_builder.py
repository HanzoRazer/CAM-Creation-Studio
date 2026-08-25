"""Operation-definition builders (CS-012)."""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_engrave,
    define_pocket,
    define_reference,
    define_slot,
)
from cam_creation_studio.operations.enums import (
    ContourRelation,
    CutDirection,
    SlotRelation,
)
from cam_creation_studio.operations.errors import OperationDefinitionError
from cam_creation_studio.operations.ids import make_operation_definition_id
from cam_creation_studio.operations.models import ReferenceDefinition
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


def test_define_contour_records_planning_parameters():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(
        workspace, "op-contour", 6.0,
        relation=ContourRelation.OUTSIDE,
        direction=CutDirection.CLIMB,
        stock_allowance_mm=0.5,
        id="def-1",
    )
    assert definition.id == "def-1"
    assert definition.intent_id == "op-contour"
    assert definition.target_depth_mm == 6.0
    assert definition.relation is ContourRelation.OUTSIDE
    assert definition.direction is CutDirection.CLIMB
    assert definition.stock_allowance_mm == 0.5


def test_contour_accepts_all_relations_and_directions():
    workspace = _workspace_with(OperationKind.CONTOUR)
    for relation in ContourRelation:
        definition = define_contour(
            workspace, "op-contour", 1.0, relation=relation)
        assert definition.relation is relation
    for direction in CutDirection:
        definition = define_contour(
            workspace, "op-contour", 1.0, direction=direction)
        assert definition.direction is direction


def test_contour_stock_allowance_zero_is_valid():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(
        workspace, "op-contour", 2.0, stock_allowance_mm=0.0)
    assert definition.stock_allowance_mm == 0.0


def test_contour_negative_allowance_is_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR)
    with pytest.raises(OperationDefinitionError, match="stock_allowance_mm"):
        define_contour(
            workspace, "op-contour", 2.0, stock_allowance_mm=-0.1)


def test_define_pocket_records_allowances_and_direction():
    workspace = _workspace_with(OperationKind.POCKET)
    definition = define_pocket(
        workspace, "op-pocket", 8.0,
        direction="conventional",
        wall_allowance_mm=0.2,
        floor_allowance_mm=0.0,
    )
    assert definition.direction is CutDirection.CONVENTIONAL
    assert definition.wall_allowance_mm == 0.2
    assert definition.floor_allowance_mm == 0.0


def test_pocket_negative_allowance_is_rejected():
    workspace = _workspace_with(OperationKind.POCKET)
    with pytest.raises(OperationDefinitionError, match="wall_allowance_mm"):
        define_pocket(workspace, "op-pocket", 4.0, wall_allowance_mm=-1)
    with pytest.raises(OperationDefinitionError, match="floor_allowance_mm"):
        define_pocket(workspace, "op-pocket", 4.0, floor_allowance_mm=-0.01)


def test_define_drill_records_retract_and_peck():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = define_drill(
        workspace, "op-drill", 12.0,
        retract_height_mm=0.0,
        peck_depth_mm=3.0,
    )
    assert definition.retract_height_mm == 0.0
    assert definition.peck_depth_mm == 3.0


def test_drill_zero_or_negative_peck_is_rejected():
    workspace = _workspace_with(OperationKind.DRILL)
    with pytest.raises(OperationDefinitionError, match="peck_depth_mm"):
        define_drill(workspace, "op-drill", 10.0, peck_depth_mm=0.0)
    with pytest.raises(OperationDefinitionError, match="peck_depth_mm"):
        define_drill(workspace, "op-drill", 10.0, peck_depth_mm=-1.0)


def test_drill_negative_retract_is_rejected():
    workspace = _workspace_with(OperationKind.DRILL)
    with pytest.raises(OperationDefinitionError, match="retract_height_mm"):
        define_drill(workspace, "op-drill", 10.0, retract_height_mm=-0.5)


def test_drill_peck_may_exceed_target_depth():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = define_drill(
        workspace, "op-drill", 2.0, peck_depth_mm=5.0)
    assert definition.peck_depth_mm == 5.0
    assert definition.peck_depth_mm > definition.target_depth_mm


def test_define_engrave_is_depth_only():
    workspace = _workspace_with(OperationKind.ENGRAVE)
    definition = define_engrave(workspace, "op-engrave", 0.2)
    assert definition.target_depth_mm == 0.2
    assert not hasattr(definition, "relation")


def test_define_slot_records_finished_width():
    workspace = _workspace_with(OperationKind.SLOT)
    definition = define_slot(
        workspace, "op-slot", 5.0, slot_width_mm=6.35, direction="climb")
    assert definition.slot_width_mm == 6.35
    assert definition.relation is SlotRelation.ON_PATH
    assert definition.direction is CutDirection.CLIMB


def test_slot_zero_or_negative_width_is_rejected():
    workspace = _workspace_with(OperationKind.SLOT)
    with pytest.raises(OperationDefinitionError, match="slot_width_mm"):
        define_slot(workspace, "op-slot", 3.0, slot_width_mm=0.0)
    with pytest.raises(OperationDefinitionError, match="slot_width_mm"):
        define_slot(workspace, "op-slot", 3.0, slot_width_mm=-2.0)


def test_define_reference_has_no_depth():
    workspace = _workspace_with(OperationKind.REFERENCE)
    definition = define_reference(workspace, "op-reference", id="ref-1")
    assert isinstance(definition, ReferenceDefinition)
    assert definition.id == "ref-1"
    assert not hasattr(definition, "target_depth_mm")


@pytest.mark.parametrize("depth", [0.0, -1.0, -6.0])
def test_machining_depth_must_be_positive(depth):
    workspace = _workspace_with(
        OperationKind.CONTOUR, OperationKind.POCKET, OperationKind.DRILL,
        OperationKind.ENGRAVE, OperationKind.SLOT)
    builders = (
        (define_contour, "op-contour"),
        (define_pocket, "op-pocket"),
        (define_drill, "op-drill"),
        (define_engrave, "op-engrave"),
        (define_slot, "op-slot"),
    )
    for builder, intent_id in builders:
        with pytest.raises(OperationDefinitionError, match="target_depth_mm"):
            builder(workspace, intent_id, depth)


def test_positive_depth_is_valid_for_every_machining_kind():
    workspace = _workspace_with(
        OperationKind.CONTOUR, OperationKind.POCKET, OperationKind.DRILL,
        OperationKind.ENGRAVE, OperationKind.SLOT)
    assert define_contour(workspace, "op-contour", 0.001).target_depth_mm == 0.001
    assert define_pocket(workspace, "op-pocket", 1.0).target_depth_mm == 1.0
    assert define_drill(workspace, "op-drill", 12.0).target_depth_mm == 12.0
    assert define_engrave(workspace, "op-engrave", 0.2).target_depth_mm == 0.2
    assert define_slot(workspace, "op-slot", 3.5).target_depth_mm == 3.5


def test_nan_and_inf_depths_are_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR)
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(OperationDefinitionError, match="finite"):
            define_contour(workspace, "op-contour", value)


def test_boolean_depth_is_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR)
    with pytest.raises(OperationDefinitionError, match="finite"):
        define_contour(workspace, "op-contour", True)  # type: ignore[arg-type]


def test_kind_mismatch_is_rejected():
    workspace = _workspace_with(OperationKind.POCKET)
    with pytest.raises(OperationDefinitionError, match="contour"):
        define_contour(workspace, "op-pocket", 6.0)


def test_missing_intent_is_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR)
    with pytest.raises(OperationDefinitionError, match="unknown operation intent"):
        define_contour(workspace, "op-missing", 6.0)


def test_unknown_enum_value_is_rejected():
    workspace = _workspace_with(OperationKind.CONTOUR, OperationKind.SLOT)
    with pytest.raises(OperationDefinitionError, match="contour relation"):
        define_contour(workspace, "op-contour", 1.0, relation="left")
    with pytest.raises(OperationDefinitionError, match="cut direction"):
        define_contour(workspace, "op-contour", 1.0, direction="both")
    with pytest.raises(OperationDefinitionError, match="slot relation"):
        define_slot(workspace, "op-slot", 1.0, relation="centered")


def test_enum_value_strings_are_coerced():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(
        workspace, "op-contour", 1.0, relation="inside", direction="climb")
    assert definition.relation is ContourRelation.INSIDE
    assert definition.direction is CutDirection.CLIMB


def test_generated_id_uses_creation_context():
    workspace = _workspace_with(OperationKind.CONTOUR)
    first = define_contour(workspace, "op-contour", 6.0)
    later = define_contour(workspace, "op-contour", 6.0, existing_count=1)
    assert first.id == make_operation_definition_id(
        "contour", "op-contour", existing_count=0)
    assert first.id != later.id
    again = define_contour(workspace, "op-contour", 6.0)
    assert again.id == first.id


def test_explicit_id_is_kept():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = define_drill(workspace, "op-drill", 5.0, id="hole-a")
    assert definition.id == "hole-a"


def test_empty_explicit_id_is_rejected():
    workspace = _workspace_with(OperationKind.ENGRAVE)
    with pytest.raises(OperationDefinitionError, match="definition ID"):
        define_engrave(workspace, "op-engrave", 0.2, id="")
