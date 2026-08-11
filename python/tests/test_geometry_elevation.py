"""Elevation fidelity for the two 2D polyline representations (CS-008R F5).

DXF gives a flat profile a height in a place that depends on which polyline the
authoring tool emitted:

* ``LWPOLYLINE`` — a scalar ``dxf.elevation``;
* 2D ``POLYLINE`` — a *point* ``dxf.elevation`` whose z holds the value, with
  every vertex at z = 0;
* 3D ``POLYLINE`` — no elevation at all; z lives on each vertex.

Reading the first two as if their vertices already carried z flattened them to
z = 0. Comparing either against the third then manufactured an asymmetry that
does not exist, which is the analytical error audit probe P8c disproved.

**Elevation is the vertices' OCS z, not a value to add afterwards.** The mapper
mixes the axes: under extrusion ``(0,0,-1)`` an OCS z of 25 resolves to a WCS z
of −25, and a tilted extrusion moves x and y too. Several tests here assert the
*sign* rather than mere presence, because an implementation that transformed a
flat point and added elevation afterwards would satisfy a weaker assertion while
being wrong on every non-default extrusion.

Audited defect: CS-008R F5, docs/audits/CS-008_REAUDIT.md.
"""

from __future__ import annotations

import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from ezdxf.math import OCS  # noqa: E402

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]

DEFAULT = (0.0, 0.0, 1.0)
FLIPPED = (0.0, 0.0, -1.0)
TILTED = (0.3, 0.4, 0.8660254037844387)


def _doc(populate, insunits=4):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = insunits
    populate(doc.modelspace())
    return doc


def _import(populate, tmp_path, insunits=4, name="elev.dxf"):
    path = str(tmp_path / name)
    _doc(populate, insunits).saveas(path)
    return import_dxf(path)


def _polylines(collection):
    return [e for e in collection.entities if e.kind == "polyline"]


def _add_pair(msp, elevation, extrusion):
    """The same authored square at the same height, in both representations."""
    msp.add_lwpolyline(SQUARE, close=True,
                       dxfattribs={"elevation": elevation, "extrusion": extrusion})
    msp.add_polyline2d(SQUARE, close=True,
                       dxfattribs={"elevation": (0, 0, elevation),
                                   "extrusion": extrusion})


# --------------------------------------------------------------------------- #
# The committed fixtures — the replacement for the withdrawn control
# --------------------------------------------------------------------------- #
def test_lwpolyline_fixture_carries_its_elevation():
    collection = import_dxf(os.path.join(FIXTURES, "lwpolyline_elevation.dxf"))
    polyline = _polylines(collection)[0]
    assert [p.z for p in polyline.vertices] == [25.0] * 4


def test_polyline2d_fixture_carries_the_same_elevation():
    collection = import_dxf(os.path.join(FIXTURES, "polyline2d_elevation.dxf"))
    polyline = _polylines(collection)[0]
    assert [p.z for p in polyline.vertices] == [25.0] * 4


def test_the_two_committed_fixtures_agree():
    """The invariant the withdrawn fixture got wrong, now committed as evidence."""
    lw = _polylines(import_dxf(os.path.join(FIXTURES, "lwpolyline_elevation.dxf")))[0]
    p2 = _polylines(import_dxf(os.path.join(FIXTURES, "polyline2d_elevation.dxf")))[0]
    assert [(p.x, p.y, p.z) for p in lw.vertices] == \
           [(p.x, p.y, p.z) for p in p2.vertices]


# --------------------------------------------------------------------------- #
# D4 — equivalent authored geometry normalizes equivalently.
#
# The matrix is the regression guard for the withdrawn asymmetry claim: units x
# extrusion x elevation sign, each case checked both against the other
# representation and against ezdxf's own transform as an independent oracle.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("units,insunits,scale", [("mm", 4, 1.0), ("inch", 1, 25.4)])
@pytest.mark.parametrize("extrusion", [DEFAULT, FLIPPED, TILTED],
                         ids=["default", "flipped", "tilted"])
@pytest.mark.parametrize("elevation", [0.0, 25.0, -12.5],
                         ids=["zero", "positive", "negative"])
def test_both_representations_match_each_other_and_ezdxf(
        units, insunits, scale, extrusion, elevation, tmp_path):
    collection = _import(lambda m: _add_pair(m, elevation, extrusion), tmp_path,
                         insunits=insunits, name=f"{units}.dxf")
    lw, p2 = _polylines(collection)

    for a, b in zip(lw.vertices, p2.vertices):
        assert (a.x, a.y, a.z) == pytest.approx((b.x, b.y, b.z), abs=1e-9), \
            "the two 2D representations must resolve identically"

    ocs = OCS(extrusion)
    for vertex, (x, y) in zip(lw.vertices, SQUARE):
        expected = ocs.to_wcs((x, y, elevation))
        assert (vertex.x, vertex.y, vertex.z) == pytest.approx(
            (expected.x * scale, expected.y * scale, expected.z * scale), abs=1e-6)


# --------------------------------------------------------------------------- #
# Sign sensitivity — what separates a correct fix from a plausible one
# --------------------------------------------------------------------------- #
def test_flipped_extrusion_negates_elevation(tmp_path):
    """Transform-then-add would land at +25 here and look like a pass."""
    collection = _import(
        lambda m: m.add_lwpolyline([(10, 4)], dxfattribs={"elevation": 25.0,
                                                          "extrusion": FLIPPED}),
        tmp_path)
    vertex = _polylines(collection)[0].vertices[0]
    assert vertex.z == pytest.approx(-25.0)
    assert vertex.x == pytest.approx(-10.0), "XY still mirrors"


def test_tilted_extrusion_moves_elevation_into_x_and_y(tmp_path):
    """A tilted plane means elevation is not purely a z contribution."""
    collection = _import(
        lambda m: m.add_lwpolyline([(0, 0)], dxfattribs={"elevation": 25.0,
                                                         "extrusion": TILTED}),
        tmp_path)
    vertex = _polylines(collection)[0].vertices[0]
    expected = OCS(TILTED).to_wcs((0, 0, 25.0))
    assert (vertex.x, vertex.y, vertex.z) == pytest.approx(
        (expected.x, expected.y, expected.z), abs=1e-9)
    assert abs(vertex.x) > 1e-6 or abs(vertex.y) > 1e-6, \
        "elevation alone should have displaced x/y on a tilted plane"


def test_elevation_scales_exactly_once(tmp_path):
    collection = _import(
        lambda m: m.add_lwpolyline([(0, 0)], dxfattribs={"elevation": 2.0}),
        tmp_path, insunits=1)                                    # inches
    assert collection.metadata.unit_scale == 25.4
    assert _polylines(collection)[0].vertices[0].z == pytest.approx(2.0 * 25.4)


# --------------------------------------------------------------------------- #
# Neighbouring behaviour that must not shift
# --------------------------------------------------------------------------- #
def test_zero_elevation_is_silent_and_planar(tmp_path):
    collection = _import(lambda m: _add_pair(m, 0.0, DEFAULT), tmp_path)
    assert [d.code for d in collection.diagnostics] == []
    assert all(p.z == 0.0 for e in _polylines(collection) for p in e.vertices)


def test_elevation_does_not_suppress_the_non_planar_finding(tmp_path):
    collection = _import(
        lambda m: m.add_lwpolyline(SQUARE, close=True,
                                   dxfattribs={"elevation": 25.0,
                                               "extrusion": TILTED}),
        tmp_path)
    assert diag.NON_PLANAR_GEOMETRY in [d.code for d in collection.diagnostics]


def test_elevated_polyline_keeps_closure_and_bulge_reporting(tmp_path):
    def build(msp):
        pl = msp.add_lwpolyline([(0, 0, 0.5), (10, 0, 0), (10, 10, 0)],
                                format="xyb", close=True)
        pl.dxf.elevation = 25.0

    collection = _import(build, tmp_path)
    polyline = _polylines(collection)[0]
    assert polyline.closed is True
    assert all(p.z == 25.0 for p in polyline.vertices)
    assert diag.POLYLINE_BULGE_IGNORED in [d.code for d in collection.diagnostics]


def test_xy_bounds_come_from_the_resolved_wcs_xy(tmp_path):
    collection = _import(lambda m: _add_pair(m, 25.0, FLIPPED), tmp_path)
    bounds = _polylines(collection)[0].bounds
    assert (bounds.min_x, bounds.max_x) == pytest.approx((-10.0, 0.0))
    assert (bounds.min_z, bounds.max_z) == pytest.approx((-25.0, -25.0))


def test_elevation_survives_serialization(tmp_path):
    from cam_creation_studio.geometry.models import GeometryCollection
    collection = _import(lambda m: _add_pair(m, 25.0, DEFAULT), tmp_path)
    restored = GeometryCollection.from_dict(collection.to_dict())
    assert [p.z for p in _polylines(restored)[0].vertices] == [25.0] * 4


def test_import_of_an_elevated_file_is_deterministic(tmp_path):
    path = str(tmp_path / "det.dxf")
    _doc(lambda m: _add_pair(m, 25.0, FLIPPED)).saveas(path)
    assert import_dxf(path).to_dict() == import_dxf(path).to_dict()


# --------------------------------------------------------------------------- #
# D5 — the other POLYLINE families are untouched by this change
# --------------------------------------------------------------------------- #
def test_polyline3d_still_carries_z_on_its_vertices(tmp_path):
    collection = _import(
        lambda m: m.add_polyline3d([(0, 0, 25), (10, 0, 25)]), tmp_path)
    assert [p.z for p in _polylines(collection)[0].vertices] == [25.0, 25.0]


def test_polyline3d_is_not_given_an_elevation(tmp_path):
    """It has no elevation attribute; reading one would double-count its z."""
    def build(msp):
        p3 = msp.add_polyline3d([(0, 0, 25), (10, 0, 25)])
        assert not p3.dxf.hasattr("elevation"), "fixture precondition"

    collection = _import(build, tmp_path)
    assert [p.z for p in _polylines(collection)[0].vertices] == [25.0, 25.0]


def test_mesh_polylines_are_still_untransformed(tmp_path):
    def build(msp):
        mesh = msp.add_polymesh(size=(2, 2), dxfattribs={"extrusion": FLIPPED})
        for m_i, n_i in ((0, 0), (0, 1), (1, 0), (1, 1)):
            mesh.set_mesh_vertex((m_i, n_i), (10 + m_i, 4 + n_i, 0))

    collection = _import(build, tmp_path)
    assert [p.x for p in _polylines(collection)[0].vertices] == [10.0, 10.0, 11.0, 11.0]
