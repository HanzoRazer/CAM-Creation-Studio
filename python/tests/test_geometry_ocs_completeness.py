"""Post-F1 OCS hardening — the gaps left open by CS-008R F1 (#14).

F1 resolved OCS -> WCS for the mainstream entity path. Reviewing the merged change
surfaced residual defects in the same resolution machinery:

* **R2 (regression)** POLYLINE *mesh* flavours were mirrored wrongly. Polygon and
  polyface meshes store WCS vertices but report ``is_3d_polyline`` False, so the F1
  guard missed them. Before F1 they were not transformed at all, so F1 made these
  worse; that is why this fix follows immediately.
* **R1** a *tilted* extrusion on LWPOLYLINE / 2D POLYLINE resolved silently. ARC
  and CIRCLE already reported non-planarity; the chain types did not, though their
  XY projection is foreshortened by the same mechanism.
* **R4** ``entity.ocs()`` was guarded, but the ``to_wcs(...)`` applications were
  not, so a mapper raising on *apply* aborted the whole import.
* **R3** ``_PLANAR_EPS`` is deliberately left unchanged; its boundary is pinned so
  a later retune is a visible decision rather than silent drift.

Diagnostic split introduced here: ``OCS_TRANSFORM_FAILED`` now means the transform
could not be obtained or applied, and ``NON_PLANAR_GEOMETRY`` means it succeeded
but the 2D model cannot represent the result faithfully. A transform that worked is
never reported as failed.

**Out of scope, deliberately:** LWPOLYLINE/POLYLINE elevation (F5), handle
traceability (F6) and ``MISSING_LAYER`` (F7) remain unremediated and belong to the
separately authorized audit-parented order.

Parent artifact: docs/audits/CS-008_REAUDIT.md
"""

from __future__ import annotations

import math
import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from ezdxf.math import OCS  # noqa: E402

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry.entities import translate  # noqa: E402

FLIPPED = (0.0, 0.0, -1.0)
TILTED = (0.3, 0.4, 0.8660254037844387)   # unit vector, clearly off-axis


def _msp():
    return ezdxf.new("R2010").modelspace()


def _codes(diags):
    return [d.code for d in diags]


# --------------------------------------------------------------------------- #
# R2 (regression) — mesh POLYLINE flavours store WCS vertices already.
# --------------------------------------------------------------------------- #
def test_polygon_mesh_vertices_match_pre_f1_wcs_coordinates():
    """Requirement 1: numerically identical to what main produced before #14."""
    mesh = _msp().add_polymesh(size=(2, 2), dxfattribs={"extrusion": FLIPPED})
    for m, n in ((0, 0), (0, 1), (1, 0), (1, 1)):
        mesh.set_mesh_vertex((m, n), (10 + m, 4 + n, 0))
    assert mesh.is_polygon_mesh and not mesh.is_3d_polyline, "fixture precondition"

    model, diags = translate(mesh, 1.0)
    assert [(p.x, p.y, p.z) for p in model.vertices] == [
        (10.0, 4.0, 0.0), (10.0, 5.0, 0.0), (11.0, 4.0, 0.0), (11.0, 5.0, 0.0)]
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags)
    assert diag.NON_PLANAR_GEOMETRY not in _codes(diags)


def test_polyface_mesh_receives_the_same_exclusion():
    """Requirement 2."""
    pf = _msp().add_polyface(dxfattribs={"extrusion": FLIPPED})
    pf.append_face([(10, 4, 0), (20, 4, 0), (20, 14, 0)])
    assert pf.is_poly_face_mesh and not pf.is_3d_polyline, "fixture precondition"

    model, diags = translate(pf, 1.0)
    # A polyface also carries a face-record vertex (at the origin) after the three
    # geometric ones, so assert the authored vertices explicitly rather than by
    # sign — under the R2 defect these came back negated.
    assert [(p.x, p.y, p.z) for p in model.vertices][:3] == [
        (10.0, 4.0, 0.0), (20.0, 4.0, 0.0), (20.0, 14.0, 0.0)]
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags)


def test_ordinary_2d_polyline_is_still_transformed():
    """Requirement 3 — the R2 fix must not over-reach into the genuine OCS case."""
    p = _msp().add_polyline2d([(10, 4), (20, 4)], dxfattribs={"extrusion": FLIPPED})
    model, diags = translate(p, 1.0)
    assert [(p.x, p.y) for p in model.vertices] == [
        pytest.approx((-10.0, 4.0), abs=1e-9), pytest.approx((-20.0, 4.0), abs=1e-9)]
    assert _codes(diags) == []


def test_polyline3d_preserves_all_three_axes_and_stays_quiet():
    """Requirement 4 — asserted on x, y and z rather than x alone."""
    p3 = _msp().add_polyline3d([(10, 4, 2), (20, 14, 3)],
                               dxfattribs={"extrusion": FLIPPED})
    model, diags = translate(p3, 1.0)
    assert [(p.x, p.y, p.z) for p in model.vertices] == [
        (10.0, 4.0, 2.0), (20.0, 14.0, 3.0)]
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags)
    assert diag.NON_PLANAR_GEOMETRY not in _codes(diags)


# --------------------------------------------------------------------------- #
# R1 — a tilted chain is placed correctly but is no longer an XY profile.
# --------------------------------------------------------------------------- #
def _tilted_chain_case(add):
    ent = add()
    model, diags = translate(ent, 1.0)
    ocs = OCS(TILTED)
    expected = [tuple(ocs.to_wcs((x, y, 0.0))) for x, y in ((0, 0), (10, 0))]
    got = [(p.x, p.y, p.z) for p in model.vertices]
    for g, e in zip(got, expected):
        assert g == pytest.approx(e, abs=1e-9)
    return diags


def test_tilted_lwpolyline_transforms_each_vertex_and_reports_non_planar():
    """Requirement 5 — correct coordinates *and* the new diagnostic."""
    diags = _tilted_chain_case(
        lambda: _msp().add_lwpolyline([(0, 0), (10, 0)],
                                      dxfattribs={"extrusion": TILTED}))
    assert diag.NON_PLANAR_GEOMETRY in _codes(diags)
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags), (
        "the transform succeeded; reporting it as failed would be false evidence")


def test_tilted_polyline2d_transforms_each_vertex_and_reports_non_planar():
    """Requirement 6."""
    diags = _tilted_chain_case(
        lambda: _msp().add_polyline2d([(0, 0), (10, 0)],
                                      dxfattribs={"extrusion": TILTED}))
    assert diag.NON_PLANAR_GEOMETRY in _codes(diags)
    assert diag.OCS_TRANSFORM_FAILED not in _codes(diags)


def test_tilted_chain_xy_projection_is_actually_foreshortened():
    """Why the diagnostic is owed: the authored shape is not recoverable planar."""
    lw = _msp().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)],
                               close=True, dxfattribs={"extrusion": TILTED})
    model, diags = translate(lw, 1.0)
    v = model.vertices
    edges = [math.dist((v[i].x, v[i].y), (v[(i + 1) % 4].x, v[(i + 1) % 4].y))
             for i in range(4)]
    assert not all(math.isclose(e, 10.0, abs_tol=1e-9) for e in edges), (
        "expected a foreshortened XY projection")
    assert diag.NON_PLANAR_GEOMETRY in _codes(diags)


def test_flipped_chain_is_planar_and_stays_quiet():
    """A mirror keeps the plane parallel to XY — nothing to report."""
    lw = _msp().add_lwpolyline([(0, 0), (10, 0)], dxfattribs={"extrusion": FLIPPED})
    model, diags = translate(lw, 1.0)
    assert _codes(diags) == []
    assert model.vertices[1].x == pytest.approx(-10.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# Degraded OCS resolution — branches F1 left entirely uncovered.
# These are genuine failures and keep OCS_TRANSFORM_FAILED.
# --------------------------------------------------------------------------- #
class _StubDxf:
    center = (10.0, 4.0, 0.0)
    radius = 5.0
    extrusion = FLIPPED
    handle = "AB"
    layer = "0"


class _NoOcs:
    dxf = _StubDxf()

    def dxftype(self):
        return "CIRCLE"


class _OcsRaises(_NoOcs):
    def ocs(self):
        raise RuntimeError("simulated OCS construction failure")


class _MapperRaises(_NoOcs):
    def ocs(self):
        class _O:
            @staticmethod
            def to_wcs(_v):
                raise RuntimeError("simulated failure applying the transform")
        return _O()


def test_missing_ocs_reports_failure_without_aborting_import():
    """Requirement 7."""
    model, diags = translate(_NoOcs(), 1.0)
    assert diag.OCS_TRANSFORM_FAILED in _codes(diags)
    assert (model.center.x, model.center.y) == (10.0, 4.0), "left untransformed"


def test_ocs_construction_raising_reports_failure():
    """Requirement 8."""
    model, diags = translate(_OcsRaises(), 1.0)
    assert diag.OCS_TRANSFORM_FAILED in _codes(diags)
    assert model is not None


def test_mapper_raising_on_apply_reports_rather_than_escaping_the_importer():
    """Requirement 9 (R4) — obtaining .to_wcs succeeds; applying it raises."""
    model, diags = translate(_MapperRaises(), 1.0)
    assert diag.OCS_TRANSFORM_FAILED in _codes(diags)
    assert (model.center.x, model.center.y) == (10.0, 4.0)


# --------------------------------------------------------------------------- #
# R3 — tolerance boundary, pinned rather than changed.
#
# The epsilon is deliberately tight: it errs toward reporting a near-planar
# extrusion rather than silently treating it as planar, the safe direction for an
# importer whose contract is "never silently wrong". Changing it is a policy
# decision that should break these tests.
# --------------------------------------------------------------------------- #
def test_extrusion_immediately_inside_tolerance_is_treated_as_default():
    """Requirement 10a."""
    c = _msp().add_circle((10, 4), radius=5,
                          dxfattribs={"extrusion": (0.0, 0.0, 1.0 - 1e-10)})
    model, diags = translate(c, 1.0)
    assert _codes(diags) == []
    assert model.center.x == pytest.approx(10.0, abs=1e-9)


def test_extrusion_immediately_outside_tolerance_is_reported_non_planar():
    """Requirement 10b."""
    c = _msp().add_circle((10, 4), radius=5,
                          dxfattribs={"extrusion": (0.0, 0.0, 1.0 - 1e-8)})
    _, diags = translate(c, 1.0)
    assert diag.NON_PLANAR_GEOMETRY in _codes(diags)


# --------------------------------------------------------------------------- #
# Requirement 11 — pin the already-verified flipped-arc wraparound geometry.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("start,end", [
    (0, 90), (350, 10), (270, 45), (0, 359), (-30, 30), (45, 405),
])
def test_flipped_arc_endpoints_are_correct_across_wraparound(start, end):
    cx, cy, r = 10.0, 4.0, 5.0
    arc = _msp().add_arc((cx, cy), radius=r, start_angle=start, end_angle=end,
                         dxfattribs={"extrusion": FLIPPED})
    model, _ = translate(arc, 1.0)
    ocs = OCS(FLIPPED)

    def wcs_image(angle):
        p = (cx + r * math.cos(math.radians(angle)),
             cy + r * math.sin(math.radians(angle)), 0.0)
        w = ocs.to_wcs(p)
        return (w.x, w.y)

    def point_at(angle):
        return (model.center.x + model.radius * math.cos(math.radians(angle)),
                model.center.y + model.radius * math.sin(math.radians(angle)))

    # The mirror reverses handedness, so the imported CCW arc starts at the image
    # of the source END and finishes at the image of the source START.
    assert point_at(model.start_angle) == pytest.approx(wcs_image(end), abs=1e-9)
    assert point_at(model.end_angle) == pytest.approx(wcs_image(start), abs=1e-9)
    assert (model.end_angle - model.start_angle) % 360 == pytest.approx(
        (end - start) % 360, abs=1e-9)


def test_mirrored_arc_angles_are_not_normalized_to_0_360():
    """Pins a real output contract, without endorsing it.

    The mirror can emit negative angles. Every in-repo consumer normalizes first
    (``bounds._angle_in_sweep``), so this is safe today; the test exists so a
    future consumer assuming [0, 360) fails here rather than in the field.
    """
    arc = _msp().add_arc((10, 4), radius=5, start_angle=350, end_angle=10,
                         dxfattribs={"extrusion": FLIPPED})
    model, _ = translate(arc, 1.0)
    assert model.end_angle < 0.0
    assert model.bounds is not None, "bounds must tolerate non-normalized angles"


# --------------------------------------------------------------------------- #
# Requirement 12 — default extrusion behaviour is untouched by this pass.
# --------------------------------------------------------------------------- #
def test_default_extrusion_entities_are_unchanged_and_quiet(tmp_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_circle((10, 4), radius=5)
    msp.add_arc((10, 4), radius=5, start_angle=0, end_angle=90)
    msp.add_lwpolyline([(0, 0), (10, 0)])
    msp.add_polyline2d([(0, 0), (10, 0)])
    path = os.path.join(str(tmp_path), "default.dxf")
    doc.saveas(path)

    col = import_dxf(path)
    codes = [d.code for d in col.diagnostics]
    assert diag.OCS_TRANSFORM_FAILED not in codes
    assert diag.NON_PLANAR_GEOMETRY not in codes


# --------------------------------------------------------------------------- #
# F5 remains unremediated. Pinned so nobody reads F1 + this pass as "OCS done".
# --------------------------------------------------------------------------- #
def test_lwpolyline_elevation_is_still_dropped():
    """Known limitation, deliberately preserved.

    Update this test as part of the F5 remediation, not incidentally while
    touching these branches for some other reason.
    """
    lw = _msp().add_lwpolyline([(10, 4), (20, 4)],
                               dxfattribs={"elevation": 7.5, "extrusion": FLIPPED})
    model, _ = translate(lw, 1.0)
    assert all(p.z == 0.0 for p in model.vertices), (
        "elevation is CS-008R F5 and remains unremediated")
