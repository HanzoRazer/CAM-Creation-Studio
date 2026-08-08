"""OCS -> WCS coordinate-correctness tests (CS-008R F1).

DXF stores CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE coordinates in the entity's
Object Coordinate System. A non-default extrusion — the ordinary result of
mirroring or rotating in CAD — means those numbers are not world coordinates.
Before F1 the importer consumed them as if they were, so mirrored geometry was
placed confidently in the wrong location with no diagnostic.

Expected coordinates here are derived from ezdxf's own OCS implementation, which
is the authority for the transform, and the pivotal (0,0,-1) case is additionally
pinned to hand-computed values so the suite does not merely assert that ezdxf
agrees with itself.

Audited defect: CS-008R F1, docs/audits/CS-008_REAUDIT.md, at 637a0ca.
"""

from __future__ import annotations

import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from ezdxf.math import OCS  # noqa: E402

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402

FLIPPED = (0, 0, -1)
TILTED = (0.3, 0.4, 0.8660254037844387)   # unit-ish, clearly off-axis


def _save(doc, tmp_path, name="ocs.dxf"):
    path = os.path.join(str(tmp_path), name)
    doc.saveas(path)
    return path


def _doc(populate, insunits=4):
    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = insunits
    populate(doc.modelspace())
    return doc


def _codes(collection):
    return [d.code for d in collection.diagnostics]


# --------------------------------------------------------------------------- #
# Default extrusion must be completely unaffected by F1
# --------------------------------------------------------------------------- #

def test_default_extrusion_circle_unchanged(tmp_path):
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2))
    col = import_dxf(_save(doc, tmp_path))
    c = col.entities[0]
    assert (c.center.x, c.center.y) == pytest.approx((10.0, 4.0))
    assert diag.OCS_TRANSFORM_FAILED not in _codes(col)


def test_default_extrusion_arc_angles_unchanged(tmp_path):
    doc = _doc(lambda m: m.add_arc((0, 0), radius=5, start_angle=30, end_angle=120))
    col = import_dxf(_save(doc, tmp_path))
    a = col.entities[0]
    assert a.start_angle == pytest.approx(30.0)
    assert a.end_angle == pytest.approx(120.0)
    assert (a.center.x, a.center.y) == pytest.approx((0.0, 0.0))


def test_explicit_default_extrusion_takes_passthrough_path(tmp_path):
    # An entity that spells out the default extrusion must behave exactly like one
    # that omits it — no transform, no diagnostic.
    doc = _doc(lambda m: m.add_circle((7, 3), radius=1,
                                      dxfattribs={"extrusion": (0, 0, 1)}))
    col = import_dxf(_save(doc, tmp_path))
    assert (col.entities[0].center.x, col.entities[0].center.y) == pytest.approx((7.0, 3.0))
    assert diag.OCS_TRANSFORM_FAILED not in _codes(col)


# --------------------------------------------------------------------------- #
# Flipped extrusion (0,0,-1) — the confirmed mirror defect
# --------------------------------------------------------------------------- #

def test_flipped_extrusion_circle_matches_ezdxf_reference(tmp_path):
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    expected = OCS(FLIPPED).to_wcs((10, 4, 0))
    c = col.entities[0]
    assert c.center.x == pytest.approx(expected.x)
    assert c.center.y == pytest.approx(expected.y)


def test_flipped_extrusion_circle_matches_hand_derivation(tmp_path):
    # Independent of ezdxf: for N = (0,0,-1) the arbitrary-axis algorithm gives
    # OCS x-axis = (-1,0,0) and y-axis = (0,1,0), so (10,4) -> (-10,4).
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    c = col.entities[0]
    assert (c.center.x, c.center.y) == pytest.approx((-10.0, 4.0))
    assert c.radius == pytest.approx(2.0)


def test_flipped_extrusion_arc_centre_and_sweep(tmp_path):
    doc = _doc(lambda m: m.add_arc((10, 4), radius=5, start_angle=0, end_angle=90,
                                   dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    a = col.entities[0]
    expected = OCS(FLIPPED).to_wcs((10, 4, 0))
    assert a.center.x == pytest.approx(expected.x)
    assert a.center.y == pytest.approx(expected.y)
    # Reflection turns the CCW 0->90 OCS sweep into 90->180 CCW in WCS.
    assert a.start_angle == pytest.approx(90.0)
    assert a.end_angle == pytest.approx(180.0)


def test_flipped_extrusion_arc_endpoints_land_where_ezdxf_says(tmp_path):
    # Strongest check on the sweep: the arc's own endpoints, transformed by ezdxf,
    # must coincide with the endpoints implied by our stored angles.
    import math

    doc = _doc(lambda m: m.add_arc((10, 4), radius=5, start_angle=0, end_angle=90,
                                   dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    a = col.entities[0]
    ocs = OCS(FLIPPED)
    ref = {
        (round(ocs.to_wcs((10 + 5 * math.cos(math.radians(t)),
                           4 + 5 * math.sin(math.radians(t)), 0)).x, 9),
         round(ocs.to_wcs((10 + 5 * math.cos(math.radians(t)),
                           4 + 5 * math.sin(math.radians(t)), 0)).y, 9))
        for t in (0.0, 90.0)
    }
    ours = {
        (round(a.center.x + a.radius * math.cos(math.radians(t)), 9),
         round(a.center.y + a.radius * math.sin(math.radians(t)), 9))
        for t in (a.start_angle, a.end_angle)
    }
    assert ours == ref


def test_flipped_extrusion_lwpolyline_matches_reference(tmp_path):
    doc = _doc(lambda m: m.add_lwpolyline([(0, 0), (10, 0), (10, 5)],
                                          dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    ocs = OCS(FLIPPED)
    expected = [ocs.to_wcs((x, y, 0)) for x, y in ((0, 0), (10, 0), (10, 5))]
    for got, want in zip(col.entities[0].vertices, expected):
        assert got.x == pytest.approx(want.x)
        assert got.y == pytest.approx(want.y)


def test_flipped_extrusion_polyline2d_matches_reference(tmp_path):
    doc = _doc(lambda m: m.add_polyline2d([(0, 0), (10, 0)],
                                          dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    ocs = OCS(FLIPPED)
    expected = [ocs.to_wcs((x, y, 0)) for x, y in ((0, 0), (10, 0))]
    for got, want in zip(col.entities[0].vertices, expected):
        assert got.x == pytest.approx(want.x)


def test_polyline3d_is_not_transformed(tmp_path):
    # A 3D polyline stores WCS vertices already; applying an OCS transform to it
    # would introduce the very defect F1 removes.
    doc = _doc(lambda m: m.add_polyline3d([(0, 0, 1), (10, 0, 1)]))
    col = import_dxf(_save(doc, tmp_path))
    assert col.entities[0].vertices[1].x == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# Arbitrary tilted extrusion
# --------------------------------------------------------------------------- #

def test_tilted_extrusion_circle_centre_matches_reference(tmp_path):
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": TILTED}))
    col = import_dxf(_save(doc, tmp_path))
    c = col.entities[0]
    expected = OCS(TILTED).to_wcs((10, 4, 0))
    assert c.center.x == pytest.approx(expected.x)
    assert c.center.y == pytest.approx(expected.y)
    assert c.center.z == pytest.approx(expected.z)


def test_tilted_extrusion_circle_reports_non_planar(tmp_path):
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": TILTED}))
    col = import_dxf(_save(doc, tmp_path))
    assert diag.OCS_TRANSFORM_FAILED in _codes(col)


def test_tilted_extrusion_arc_centre_correct_and_sweep_reported(tmp_path):
    doc = _doc(lambda m: m.add_arc((10, 4), radius=5, start_angle=0, end_angle=90,
                                   dxfattribs={"extrusion": TILTED}))
    col = import_dxf(_save(doc, tmp_path))
    a = col.entities[0]
    expected = OCS(TILTED).to_wcs((10, 4, 0))
    assert (a.center.x, a.center.y, a.center.z) == pytest.approx(
        (expected.x, expected.y, expected.z))
    assert diag.OCS_TRANSFORM_FAILED in _codes(col)


def test_tilted_extrusion_lwpolyline_vertices_match_reference(tmp_path):
    doc = _doc(lambda m: m.add_lwpolyline([(0, 0), (10, 0)],
                                          dxfattribs={"extrusion": TILTED}))
    col = import_dxf(_save(doc, tmp_path))
    ocs = OCS(TILTED)
    for got, (x, y) in zip(col.entities[0].vertices, ((0, 0), (10, 0))):
        want = ocs.to_wcs((x, y, 0))
        assert (got.x, got.y, got.z) == pytest.approx((want.x, want.y, want.z))


# --------------------------------------------------------------------------- #
# Everything F1 must leave alone
# --------------------------------------------------------------------------- #

def _mixed(m):
    m.add_line((0, 0), (10, 0), dxfattribs={"layer": "cut"})
    m.add_arc((0, 0), radius=5, start_angle=0, end_angle=90,
              dxfattribs={"layer": "cut", "extrusion": FLIPPED})
    m.add_circle((20, 20), radius=3, dxfattribs={"layer": "holes", "extrusion": FLIPPED})
    m.add_lwpolyline([(0, 0), (1, 0)], dxfattribs={"layer": "cut"})


def test_source_order_unchanged(tmp_path):
    col = import_dxf(_save(_doc(_mixed), tmp_path))
    assert [e.kind for e in col.entities] == ["line", "arc", "circle", "polyline"]


def test_layer_metadata_unchanged(tmp_path):
    col = import_dxf(_save(_doc(_mixed), tmp_path))
    assert [e.layer for e in col.entities] == ["cut", "cut", "holes", "cut"]


def test_bounds_follow_corrected_wcs_coordinates(tmp_path):
    # Circle at OCS (20,20) r=3 under a flipped extrusion sits at WCS (-20,20),
    # so the box must be centred there, not at +20.
    doc = _doc(lambda m: m.add_circle((20, 20), radius=3,
                                      dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    assert col.bounds.as_tuple() == pytest.approx((-23.0, 17.0, -17.0, 23.0))


def test_unit_normalization_still_applies_after_transform(tmp_path):
    # Inches + flipped extrusion: transform first, then scale to mm.
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": FLIPPED}), insunits=1)
    col = import_dxf(_save(doc, tmp_path))
    c = col.entities[0]
    assert c.center.x == pytest.approx(-10.0 * 25.4)
    assert c.center.y == pytest.approx(4.0 * 25.4)
    assert c.radius == pytest.approx(2.0 * 25.4)


def test_serialization_round_trip_after_transform(tmp_path):
    from cam_creation_studio.geometry import GeometryCollection

    col = import_dxf(_save(_doc(_mixed), tmp_path))
    restored = GeometryCollection.from_json(col.to_json())
    assert [e.kind for e in restored.entities] == [e.kind for e in col.entities]
    assert restored.bounds.as_tuple() == pytest.approx(col.bounds.as_tuple())


def test_import_remains_deterministic(tmp_path):
    path = _save(_doc(_mixed), tmp_path)
    assert import_dxf(path).to_json() == import_dxf(path).to_json()


def test_successful_transform_is_not_reported_as_loss(tmp_path):
    # Normalizing OCS -> WCS is ordinary behaviour, not a fidelity loss: a clean
    # flipped-extrusion import must stay quiet and non-lossy.
    doc = _doc(lambda m: m.add_circle((10, 4), radius=2,
                                      dxfattribs={"extrusion": FLIPPED}))
    col = import_dxf(_save(doc, tmp_path))
    assert _codes(col) == []
    assert col.metadata.has_lossy_import is False
