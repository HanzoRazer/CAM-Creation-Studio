"""Mesh / polyface POLYLINE fidelity evidence (CS-008R-D1).

A polygon-mesh or polyface ``POLYLINE`` currently survives as a flattened
``Polyline2D`` while its source topology is discarded. That partial chain is
useful evidence, but reporting the import as lossless is the defect this suite
pins.

Two loss surfaces stay distinct, and this file locks both:

* ``ImportMetadata.has_lossy_import`` — a source entity produced no geometry.
  Mesh/polyface flattening does *not* set it: the entity is retained.
* ``ImportReport.has_loss`` — source information failed to survive. Mesh/polyface
  topology loss *must* set it.

The desired invariant, against which current ``main`` is wrong:

    retained mesh/polyface
        + exactly one POLYLINE_MESH_TOPOLOGY_DROPPED
        + report().has_loss is True
        + metadata.has_lossy_import is False

Parent artifact: ``docs/audits/CS-008R_CLOSURE.md``.
"""

from __future__ import annotations

import json
import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry.entities import translate  # noqa: E402
from cam_creation_studio.geometry.models import (  # noqa: E402
    GeometryCollection,
    Polyline2D,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# The constant lands in commit 2; tests must name the code before then.
MESH_LOSS = getattr(
    diag, "POLYLINE_MESH_TOPOLOGY_DROPPED", "POLYLINE_MESH_TOPOLOGY_DROPPED")

# Flattened chains captured from current main. Any coordinate change is a
# regression: this order changes fidelity evidence, not geometry shape.
POLYGON_MESH_VERTICES = [
    (0.0, 0.0, 0.0),
    (10.0, 0.0, 1.0),
    (20.0, 0.0, 0.0),
    (0.0, 8.0, 0.0),
    (10.0, 8.0, 2.0),
    (20.0, 8.0, 0.0),
]
POLYFACE_MESH_VERTICES = [
    (0.0, 0.0, 0.0),
    (10.0, 0.0, 0.0),
    (10.0, 10.0, 0.0),
    (0.0, 10.0, 0.0),
    (0.0, 0.0, 10.0),
    (10.0, 0.0, 10.0),
    (10.0, 10.0, 10.0),
    (0.0, 10.0, 10.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
]


def _load(name):
    return import_dxf(os.path.join(FIXTURES, name))


def _codes(obj):
    diags = obj.diagnostics if hasattr(obj, "diagnostics") else obj
    return [d.code for d in diags]


def _mesh_findings(obj):
    diags = obj.diagnostics if hasattr(obj, "diagnostics") else obj
    return [d for d in diags if d.code == MESH_LOSS]


def _xyz(entity):
    return [(p.x, p.y, p.z) for p in entity.vertices]


def _source_entity(name):
    doc = ezdxf.readfile(os.path.join(FIXTURES, name))
    return list(doc.modelspace())[0]


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def hasattr(self, name):
        return name in self.__dict__


class _FakeVertex:
    def __init__(self, location, bulge=0.0, flags=0, is_face_record=False):
        self.dxf = _NS(location=location, bulge=bulge, flags=flags)
        self.is_face_record = is_face_record


class _FakePolyline:
    """Duck-typed POLYLINE; ``translate()`` never imports ezdxf symbols."""

    def __init__(self, vertices, *, family="polygon_mesh", layer="0",
                 handle="M1", **dxf):
        self.dxf = _NS(layer=layer, handle=handle, **dxf)
        self.vertices = list(vertices)
        self.is_closed = False
        self.is_polygon_mesh = family == "polygon_mesh"
        self.is_poly_face_mesh = family == "polyface_mesh"
        self.is_3d_polyline = family == "three_d"

    def dxftype(self):
        return "POLYLINE"


# --------------------------------------------------------------------------- #
# Fixture preconditions — these must be real mesh families, not named chains.
# --------------------------------------------------------------------------- #
def test_polygon_mesh_fixture_is_a_polygon_mesh_not_a_polyline_chain():
    entity = _source_entity("polygon_mesh.dxf")
    assert entity.dxftype() == "POLYLINE"
    assert entity.is_polygon_mesh is True
    assert entity.is_poly_face_mesh is False
    assert entity.is_3d_polyline is False
    assert entity.dxf.flags == 16
    assert entity.dxf.m_count == 2
    assert entity.dxf.n_count == 3
    assert len(list(entity.vertices)) == 6


def test_polyface_mesh_fixture_carries_actual_face_records():
    entity = _source_entity("polyface_mesh.dxf")
    assert entity.dxftype() == "POLYLINE"
    assert entity.is_poly_face_mesh is True
    assert entity.is_polygon_mesh is False
    assert entity.is_3d_polyline is False
    assert entity.dxf.flags == 64
    face_records = [v for v in entity.vertices if v.is_face_record]
    geometric = [v for v in entity.vertices if not v.is_face_record]
    assert len(geometric) == 8
    assert len(face_records) == 6
    assert len(list(entity.faces())) == 6


# --------------------------------------------------------------------------- #
# Polygon mesh — retained chain + explicit unrecoverable topology loss
# --------------------------------------------------------------------------- #
def test_polygon_mesh_retains_the_current_flattened_chain():
    polyline = _load("polygon_mesh.dxf").entities[0]
    assert isinstance(polyline, Polyline2D)
    assert _xyz(polyline) == POLYGON_MESH_VERTICES


def test_polygon_mesh_emits_exactly_one_unrecoverable_topology_loss():
    collection = _load("polygon_mesh.dxf")
    findings = _mesh_findings(collection)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.is_loss is True
    assert diag.is_loss(finding.code) is True
    assert finding.recoverable is False
    assert finding.entity_type == "POLYLINE"
    assert finding.handle
    assert finding.layer == "0"
    assert finding.metadata["source_family"] == "polygon_mesh"
    if "m_count" in finding.metadata:
        assert finding.metadata["m_count"] == 2
        assert finding.metadata["n_count"] == 3
    diag.ensure_json_safe(finding.metadata)


def test_polygon_mesh_is_retained_but_lossy_on_the_report_surface():
    collection = _load("polygon_mesh.dxf")
    report = collection.report()
    assert collection.metadata.has_lossy_import is False
    assert report.has_loss is True
    assert report.loss_count >= 1
    assert report.unrecoverable_loss_count >= 1


def test_polygon_mesh_preserves_source_provenance():
    entity = _load("polygon_mesh.dxf").entities[0]
    assert entity.source is not None
    assert entity.source.entity_type == "POLYLINE"
    assert entity.source.handle
    assert entity.source.layer == "0"
    assert entity.source.ordinal == 0


# --------------------------------------------------------------------------- #
# Polyface mesh — face-record vertices stay; topology does not
# --------------------------------------------------------------------------- #
def test_polyface_mesh_retains_the_current_chain_including_face_records():
    polyline = _load("polyface_mesh.dxf").entities[0]
    assert isinstance(polyline, Polyline2D)
    assert _xyz(polyline) == POLYFACE_MESH_VERTICES
    # Six trailing origin vertices are the face records; claiming they are
    # absent would be a geometry redesign this order does not authorize.
    assert _xyz(polyline)[8:] == [(0.0, 0.0, 0.0)] * 6


def test_polyface_mesh_emits_exactly_one_unrecoverable_topology_loss():
    collection = _load("polyface_mesh.dxf")
    findings = _mesh_findings(collection)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.is_loss is True
    assert finding.recoverable is False
    assert finding.entity_type == "POLYLINE"
    assert finding.handle
    assert finding.layer == "0"
    assert finding.metadata["source_family"] == "polyface_mesh"
    # Face-record count is a source fact, not a claim that faces survived.
    if "face_record_count" in finding.metadata:
        assert finding.metadata["face_record_count"] == 6
    assert "faces_preserved" not in finding.metadata
    diag.ensure_json_safe(finding.metadata)


def test_polyface_mesh_is_retained_but_lossy_on_the_report_surface():
    collection = _load("polyface_mesh.dxf")
    report = collection.report()
    assert collection.metadata.has_lossy_import is False
    assert report.has_loss is True
    assert report.loss_count >= 1
    assert report.unrecoverable_loss_count >= 1


def test_polyface_mesh_preserves_source_provenance():
    entity = _load("polyface_mesh.dxf").entities[0]
    assert entity.source is not None
    assert entity.source.entity_type == "POLYLINE"
    assert entity.source.handle
    assert entity.source.layer == "0"
    assert entity.source.ordinal == 0


# --------------------------------------------------------------------------- #
# The two loss surfaces must not be collapsed
# --------------------------------------------------------------------------- #
def test_retained_mesh_does_not_set_the_dropped_entity_flag():
    """Mandatory contract: flattening is loss, not an omitted entity."""
    for name in ("polygon_mesh.dxf", "polyface_mesh.dxf"):
        collection = _load(name)
        assert collection.entities, name
        assert collection.metadata.has_lossy_import is False, name
        assert collection.report().has_loss is True, name


def test_dropped_unsupported_entity_still_sets_has_lossy_import():
    collection = _load("unsupported_entity.dxf")
    assert collection.metadata.has_lossy_import is True
    assert diag.UNSUPPORTED_ENTITY in _codes(collection)


# --------------------------------------------------------------------------- #
# Degenerate mesh — both facts, neither collapsed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("points", [[], [(5.0, 5.0, 0.0)]])
@pytest.mark.parametrize("family", ["polygon_mesh", "polyface_mesh"])
def test_degenerate_mesh_keeps_the_entity_and_reports_both_facts(points, family):
    vertices = [_FakeVertex(p) for p in points]
    model, diags = translate(_FakePolyline(vertices, family=family), 1.0)
    assert isinstance(model, Polyline2D)
    assert diag.DEGENERATE_POLYLINE in _codes(diags)
    assert _codes(diags).count(MESH_LOSS) == 1
    finding = _mesh_findings(diags)[0]
    assert finding.recoverable is False
    assert finding.is_loss is True


# --------------------------------------------------------------------------- #
# Ordinary POLYLINE families must not grow a mesh finding
# --------------------------------------------------------------------------- #
def test_two_d_polyline_fixture_has_no_mesh_diagnostic():
    collection = _load("polyline2d_elevation.dxf")
    assert MESH_LOSS not in _codes(collection)
    polyline = [e for e in collection.entities if e.kind == "polyline"][0]
    assert all(v.z == pytest.approx(25.0) for v in polyline.vertices)
    assert collection.report().has_loss is False


def test_lwpolyline_elevation_fixture_has_no_mesh_diagnostic():
    collection = _load("lwpolyline_elevation.dxf")
    assert MESH_LOSS not in _codes(collection)
    polyline = [e for e in collection.entities if e.kind == "polyline"][0]
    assert all(v.z == pytest.approx(25.0) for v in polyline.vertices)
    assert collection.report().has_loss is False


def test_three_d_polyline_has_no_mesh_diagnostic_and_keeps_wcs(tmp_path):
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_polyline3d([(0, 0, 25), (10, 0, 25)])
    path = str(tmp_path / "p3.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    assert MESH_LOSS not in _codes(collection)
    polyline = collection.entities[0]
    assert _xyz(polyline) == [(0.0, 0.0, 25.0), (10.0, 0.0, 25.0)]
    assert collection.report().has_loss is False
    assert collection.metadata.has_lossy_import is False


def test_flipped_mesh_coordinates_remain_untransformed():
    """PR #16: mesh vertices are already WCS and must not be mirrored."""
    mesh = ezdxf.new("R2010").modelspace().add_polymesh(
        size=(2, 2), dxfattribs={"extrusion": (0.0, 0.0, -1.0)})
    for m, n in ((0, 0), (0, 1), (1, 0), (1, 1)):
        mesh.set_mesh_vertex((m, n), (10 + m, 4 + n, 0))
    model, diags = translate(mesh, 1.0)
    assert _xyz(model) == [
        (10.0, 4.0, 0.0), (10.0, 5.0, 0.0), (11.0, 4.0, 0.0), (11.0, 5.0, 0.0)]
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags)
    assert diag.NON_PLANAR_GEOMETRY not in _codes(diags)
    assert _codes(diags).count(MESH_LOSS) == 1


# --------------------------------------------------------------------------- #
# Mixed document and F7 coexistence
# --------------------------------------------------------------------------- #
def test_mixed_file_keeps_representable_entities_and_reports_one_loss(tmp_path):
    doc = ezdxf.new("R2010")
    doc.units = 4
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    mesh = msp.add_polymesh(size=(2, 2))
    for m, n in ((0, 0), (0, 1), (1, 0), (1, 1)):
        mesh.set_mesh_vertex((m, n), (m, n, 0))
    msp.add_circle((5, 5), radius=2)
    path = str(tmp_path / "mixed.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    kinds = [e.kind for e in collection.entities]
    assert kinds == ["line", "polyline", "circle"]
    assert _codes(collection).count(MESH_LOSS) == 1
    assert collection.report().has_loss is True
    assert collection.metadata.has_lossy_import is False
    assert [e.source.ordinal for e in collection.entities] == [0, 1, 2]


def test_unknown_layer_and_mesh_topology_loss_coexist(tmp_path):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = 4
    mesh = doc.modelspace().add_polymesh(
        size=(2, 2), dxfattribs={"layer": "no-such-layer"})
    for m, n in ((0, 0), (0, 1), (1, 0), (1, 1)):
        mesh.set_mesh_vertex((m, n), (m, n, 0))
    path = str(tmp_path / "mesh_layer.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    codes = _codes(collection)
    assert diag.MISSING_LAYER in codes
    assert codes.count(MESH_LOSS) == 1
    assert MESH_LOSS in {d.code for d in collection.losses}
    assert diag.MISSING_LAYER not in {d.code for d in collection.losses}
    assert collection.entities, "layer evidence must not cost the geometry"


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def test_mesh_loss_diagnostic_round_trips_through_serialization():
    collection = _load("polygon_mesh.dxf")
    blob = json.dumps(collection.to_dict())
    restored = GeometryCollection.from_dict(json.loads(blob))
    assert json.dumps(restored.to_dict()) == blob
    finding = _mesh_findings(restored)[0]
    assert finding.code == MESH_LOSS
    assert finding.recoverable is False
    assert finding.metadata["source_family"] == "polygon_mesh"
    assert "np.float64" not in blob
    assert "numpy" not in blob
    diag.ensure_json_safe(finding.metadata)


# --------------------------------------------------------------------------- #
# Diagnostic registry — filled in by the contract commit; asserted here so the
# primary suite owns the code's meaning, not only its emission.
# --------------------------------------------------------------------------- #
def test_mesh_topology_code_is_a_registered_unrecoverable_loss():
    assert MESH_LOSS == "POLYLINE_MESH_TOPOLOGY_DROPPED"
    assert MESH_LOSS in diag.CANONICAL_CODES
    assert MESH_LOSS in diag.LOSS_CODES
    assert diag.is_loss(MESH_LOSS) is True
    assert diag.LWPOLYLINE_ELEVATION_DROPPED in diag.CANONICAL_CODES
    assert diag.LWPOLYLINE_ELEVATION_DROPPED in diag.LOSS_CODES
