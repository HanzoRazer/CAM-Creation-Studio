"""Workspace contract invariants (CS-011).

These pin the dataclasses and the closed operation vocabulary. They do not
build a workspace from a collection — that is the next increment.
"""

from __future__ import annotations

import dataclasses

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.models import (
    WORKSPACE_VERSION,
    GeometryGroup,
    GeometryRef,
    GeometrySelection,
    GeometryWorkspace,
    OperationIntent,
    OperationKind,
)


def test_workspace_version_is_the_v1_persistence_token():
    assert WORKSPACE_VERSION == "camstudio_geometry_workspace_v1"


def test_operation_kind_is_a_closed_str_enum():
    assert {k.value for k in OperationKind} == {
        "contour", "pocket", "drill", "engrave", "slot", "reference",
    }
    assert OperationKind.CONTOUR == "contour"
    assert OperationKind.REFERENCE == "reference"
    assert not hasattr(OperationKind, "UNKNOWN")


def test_unknown_operation_kind_fails_clearly():
    with pytest.raises(ValueError):
        OperationKind("plunge")


def test_contracts_are_frozen():
    for cls in (
        GeometryRef, GeometrySelection, GeometryGroup,
        OperationIntent, GeometryWorkspace,
    ):
        assert cls.__dataclass_params__.frozen is True


def test_geometry_ref_is_id_plus_source_order_index():
    ref = GeometryRef(id="geom-a", entity_index=0)
    assert ref.id == "geom-a"
    assert ref.entity_index == 0


def test_selection_and_group_preserve_explicit_member_order():
    sel = GeometrySelection(id="s1", name="outer", entity_ids=("b", "a", "c"))
    grp = GeometryGroup(
        id="g1", name="body", entity_ids=("b", "a"), description="outline")
    assert sel.entity_ids == ("b", "a", "c")
    assert grp.entity_ids == ("b", "a")
    assert grp.description == "outline"


def test_operation_intent_is_kind_plus_selection_only():
    intent = OperationIntent(
        id="op1", name="outer contour",
        kind=OperationKind.CONTOUR, selection_id="s1")
    names = {f.name for f in dataclasses.fields(intent)}
    assert names == {"id", "name", "kind", "selection_id"}


def test_workspace_defaults_to_empty_application_state():
    collection = GeometryCollection()
    workspace = GeometryWorkspace(
        version=WORKSPACE_VERSION,
        geometry=collection,
        geometry_refs=(),
    )
    assert workspace.selections == ()
    assert workspace.groups == ()
    assert workspace.operations == ()
    assert workspace.geometry is collection


def test_workspace_holds_geometry_by_reference_not_a_copy_of_points():
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    collection = GeometryCollection(entities=[line])
    workspace = GeometryWorkspace(
        version=WORKSPACE_VERSION,
        geometry=collection,
        geometry_refs=(GeometryRef(id="geom-0", entity_index=0),),
    )
    assert workspace.geometry.entities[0] is line


def test_workspace_error_is_the_structural_exception():
    assert issubclass(WorkspaceError, Exception)
    with pytest.raises(WorkspaceError, match="dangling"):
        raise WorkspaceError("dangling selection 's1'")
