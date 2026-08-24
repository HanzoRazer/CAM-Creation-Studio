"""Workspace construction from a GeometryCollection (CS-011)."""

from __future__ import annotations

from cam_creation_studio.geometry.models import (
    Arc2D,
    Circle2D,
    GeometryCollection,
    Line2D,
    Polyline2D,
    SourceReference,
    Spline2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.ids import make_workspace_entity_id
from cam_creation_studio.workspace.models import WORKSPACE_VERSION


def _src(handle, ordinal, entity_type="LINE", layer="0"):
    return SourceReference(
        entity_type=entity_type, handle=handle, layer=layer, ordinal=ordinal)


def _line(handle="A1", ordinal=0, layer="cut"):
    return Line2D(
        start=Point(0, 0), end=Point(10, 0), layer=layer,
        source=_src(handle, ordinal, "LINE", layer))


def test_empty_collection_builds_an_empty_workspace():
    workspace = build_workspace(GeometryCollection())
    assert workspace.version == WORKSPACE_VERSION
    assert workspace.geometry_refs == ()
    assert workspace.selections == ()
    assert workspace.groups == ()
    assert workspace.operations == ()


def test_one_entity_gets_a_single_ref_at_index_zero():
    line = _line()
    workspace = build_workspace(GeometryCollection(entities=[line]))
    assert len(workspace.geometry_refs) == 1
    assert workspace.geometry_refs[0].entity_index == 0
    assert workspace.geometry.entities[0] is line


def test_mixed_five_kind_collection_preserves_source_order():
    entities = [
        _line("L", 0),
        Arc2D(center=Point(0, 0), radius=5, start_angle=0, end_angle=90,
              source=_src("A", 1, "ARC")),
        Circle2D(center=Point(2, 2), radius=1, source=_src("C", 2, "CIRCLE")),
        Polyline2D(vertices=[Point(0, 0), Point(1, 1)],
                   source=_src("P", 3, "LWPOLYLINE")),
        Spline2D(control_points=[Point(0, 0), Point(1, 2), Point(2, 0), Point(3, 2)],
                 source=_src("S", 4, "SPLINE")),
    ]
    workspace = build_workspace(GeometryCollection(entities=entities))
    assert [e.kind for e in workspace.geometry.entities] == [
        "line", "arc", "circle", "polyline", "spline"]
    assert [r.entity_index for r in workspace.geometry_refs] == [0, 1, 2, 3, 4]
    assert len({r.id for r in workspace.geometry_refs}) == 5


def test_geometry_ids_are_deterministic_across_repeated_builds():
    collection = GeometryCollection(entities=[_line("L1", 0), _line("L2", 1)])
    first = build_workspace(collection)
    second = build_workspace(collection)
    assert [r.id for r in first.geometry_refs] == [r.id for r in second.geometry_refs]


def test_entity_without_dxf_handle_still_gets_a_deterministic_id():
    bare = Line2D(start=Point(0, 0), end=Point(4, 0))
    handled = _line("HH", 0)
    a = build_workspace(GeometryCollection(entities=[bare]))
    b = build_workspace(GeometryCollection(entities=[bare]))
    assert a.geometry_refs[0].id == b.geometry_refs[0].id
    assert a.geometry_refs[0].id != build_workspace(
        GeometryCollection(entities=[handled])).geometry_refs[0].id


def test_source_ordinal_gaps_do_not_break_ids():
    first = Line2D(start=Point(0, 0), end=Point(1, 0),
                   source=_src("A", 0))
    third = Line2D(start=Point(2, 0), end=Point(3, 0),
                   source=_src("C", 2))
    workspace = build_workspace(GeometryCollection(entities=[first, third]))
    assert [r.entity_index for r in workspace.geometry_refs] == [0, 1]
    assert workspace.geometry_refs[0].id != workspace.geometry_refs[1].id
    assert workspace.geometry_refs[0].id == make_workspace_entity_id(0, "A", 0)
    assert workspace.geometry_refs[1].id == make_workspace_entity_id(1, "C", 2)


def test_geometry_itself_remains_unchanged():
    line = _line()
    collection = GeometryCollection(entities=[line])
    workspace = build_workspace(collection)
    assert workspace.geometry is collection
    assert workspace.geometry.entities[0] is line
    assert workspace.geometry.entities[0] == line
