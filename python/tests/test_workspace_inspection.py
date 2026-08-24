"""Inspection exposes geometry facts, provenance, bounds, and loss (CS-011)."""

from __future__ import annotations

import os

import pytest

from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.diagnostics import GeometryDiagnostic
from cam_creation_studio.geometry.models import (
    Arc2D,
    Circle2D,
    GeometryCollection,
    ImportMetadata,
    Line2D,
    Polyline2D,
    SourceReference,
    Spline2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.inspection import (
    inspect_entity,
    inspect_workspace,
)
from cam_creation_studio.workspace.refs import resolve_entity


def _src(handle, ordinal, entity_type, layer="0"):
    return SourceReference(
        entity_type=entity_type, handle=handle, layer=layer, ordinal=ordinal)


def _collection(*entities, diagnostics=(), unsupported=0):
    return GeometryCollection(
        entities=list(entities),
        metadata=ImportMetadata(
            source_path="part.dxf", source_units="mm", unit_scale=1.0,
            entity_count=len(entities), raw_entity_count=len(entities) + unsupported,
            unsupported_entity_count=unsupported),
        diagnostics=list(diagnostics),
    )


def test_inspects_each_geometry_kind():
    entities = [
        Line2D(start=Point(0, 0), end=Point(10, 0), layer="cut",
               source=_src("L", 0, "LINE", "cut")),
        Arc2D(center=Point(0, 0), radius=5, start_angle=0, end_angle=90,
              layer="cut", source=_src("A", 1, "ARC", "cut")),
        Circle2D(center=Point(4, 4), radius=2, layer="holes",
                 source=_src("C", 2, "CIRCLE", "holes")),
        Polyline2D(vertices=[Point(0, 0), Point(1, 0), Point(1, 1)],
                   layer="cut", source=_src("P", 3, "LWPOLYLINE", "cut")),
        Spline2D(control_points=[Point(0, 0), Point(1, 2), Point(2, 0), Point(3, 2)],
                 layer="profile", source=_src("S", 4, "SPLINE", "profile")),
    ]
    workspace = build_workspace(_collection(*entities))
    kinds = []
    for ref, entity in zip(workspace.geometry_refs, entities):
        view = inspect_entity(workspace, ref.id)
        kinds.append(view.kind)
        assert view.layer == entity.layer
        assert view.source_handle == entity.source.handle
        assert view.source_ordinal == entity.source.ordinal
        assert view.bounds == entity.bounds
        assert view.has_loss is False
        assert view.diagnostic_codes == ()
    assert kinds == ["line", "arc", "circle", "polyline", "spline"]


def test_loss_diagnostic_attaches_only_by_matching_handle():
    line = Line2D(start=Point(0, 0), end=Point(0, 0),
                  source=_src("H1", 0, "LINE"))
    other = Line2D(start=Point(1, 0), end=Point(2, 0),
                   source=_src("H2", 1, "LINE"))
    finding = GeometryDiagnostic(
        DiagnosticSeverity.WARNING, diag.ZERO_LENGTH_LINE, "zero",
        entity_type="LINE", handle="H1", layer="0")
    units = GeometryDiagnostic(
        DiagnosticSeverity.INFO, diag.UNKNOWN_UNITS, "units unknown")
    workspace = build_workspace(_collection(line, other, diagnostics=[finding, units]))

    lost = inspect_entity(workspace, workspace.geometry_refs[0].id)
    clean = inspect_entity(workspace, workspace.geometry_refs[1].id)
    assert lost.diagnostic_codes == (diag.ZERO_LENGTH_LINE,)
    assert lost.has_loss is False  # ZERO_LENGTH_LINE is advisory, not a loss code
    assert clean.diagnostic_codes == ()
    assert clean.has_loss is False


def test_lossy_code_sets_has_loss_and_collection_findings_stay_off_entities():
    line = Line2D(start=Point(0, 0), end=Point(5, 0),
                  source=_src("PF", 0, "POLYLINE"))
    loss = diag.loss(
        diag.POLYLINE_MESH_TOPOLOGY_DROPPED, "topology dropped",
        recoverable=False, metadata={"source_family": "polygon_mesh"},
        entity_type="POLYLINE", handle="PF", layer="0")
    workspace = build_workspace(_collection(line, diagnostics=[loss]))
    view = inspect_entity(workspace, workspace.geometry_refs[0].id)
    assert view.has_loss is True
    assert diag.POLYLINE_MESH_TOPOLOGY_DROPPED in view.diagnostic_codes


def test_no_association_from_layer_or_type_alone():
    line = Line2D(start=Point(0, 0), end=Point(5, 0), layer="cut",
                  source=_src(None, 0, "LINE", "cut"))
    finding = GeometryDiagnostic(
        DiagnosticSeverity.WARNING, diag.ZERO_LENGTH_LINE, "zero",
        entity_type="LINE", handle="OTHER", layer="cut")
    workspace = build_workspace(_collection(line, diagnostics=[finding]))
    view = inspect_entity(workspace, workspace.geometry_refs[0].id)
    assert view.diagnostic_codes == ()
    assert view.source_handle is None


def test_duplicate_shared_handle_attaches_to_each_entity():
    a = Line2D(start=Point(0, 0), end=Point(1, 0), source=_src("DUP", 0, "LINE"))
    b = Line2D(start=Point(2, 0), end=Point(3, 0), source=_src("DUP", 1, "LINE"))
    finding = GeometryDiagnostic(
        DiagnosticSeverity.WARNING, diag.DUPLICATE_HANDLE, "dup",
        entity_type="LINE", handle="DUP")
    workspace = build_workspace(_collection(a, b, diagnostics=[finding]))
    for ref in workspace.geometry_refs:
        assert inspect_entity(workspace, ref.id).diagnostic_codes == (
            diag.DUPLICATE_HANDLE,)


def test_inspect_workspace_reports_collection_loss_without_claiming_readiness():
    line = Line2D(start=Point(0, 0), end=Point(5, 0), source=_src("X", 0, "LINE"))
    text = GeometryDiagnostic(
        DiagnosticSeverity.WARNING, diag.UNSUPPORTED_ENTITY, "TEXT",
        entity_type="TEXT", handle="T1")
    workspace = build_workspace(
        _collection(line, diagnostics=[text], unsupported=1))
    view = inspect_workspace(workspace)
    assert view.entity_count == 1
    assert view.import_loss_count == 1
    assert view.has_lossy_import is True
    assert view.selection_count == 0


def test_unknown_entity_id_raises():
    workspace = build_workspace(GeometryCollection())
    with pytest.raises(WorkspaceError, match="unknown geometry ID"):
        resolve_entity(workspace, "geom-missing")


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(os.path.dirname(__file__), "fixtures", "polygon_mesh.dxf")),
    reason="polygon_mesh fixture required",
)
def test_mesh_topology_loss_from_cs008r_d1_is_visible():
    pytest.importorskip("ezdxf")
    from cam_creation_studio.geometry import import_dxf

    path = os.path.join(os.path.dirname(__file__), "fixtures", "polygon_mesh.dxf")
    workspace = build_workspace(import_dxf(path))
    assert workspace.geometry_refs
    view = inspect_entity(workspace, workspace.geometry_refs[0].id)
    assert view.kind == "polyline"
    assert view.has_loss is True
    assert diag.POLYLINE_MESH_TOPOLOGY_DROPPED in view.diagnostic_codes
    overview = inspect_workspace(workspace)
    assert overview.import_loss_count >= 1
    assert overview.has_lossy_import is False
