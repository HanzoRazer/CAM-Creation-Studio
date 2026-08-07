"""OCS→WCS correctness and LWPOLYLINE elevation (CS-008 remediation, PR 3).

DXF stores CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE coordinates in the entity's
own object coordinate system. With the default extrusion (0,0,1) that *is* the
WCS; with any other it is not, and importing raw OCS numbers places geometry
somewhere it does not belong.

The transform comes from ezdxf's own ``entity.ocs()`` rather than a local
implementation of the arbitrary-axis algorithm — duplicating it would create a
second authority for the same maths. These tests use the duck-typed
``translate()`` entry point with a stand-in that delegates to ezdxf's real
``OCS``, so the library remains the source of truth while the fixtures stay
small.

The three cases that matter:

    default  (0,0,1)   OCS is WCS          -> untouched, byte-compatible
    mirrored (0,0,-1)  parallel to WCS XY  -> corrected exactly, silently
    tilted   (other)   out of the XY plane -> centre corrected, plane reported
"""

import math

import pytest

from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.entities import (
    DEFAULT_EXTRUSION,
    _is_planar_extrusion,
    _mirror_arc_angles,
    translate,
)
from cam_creation_studio.geometry.models import Arc2D, Circle2D, Polyline2D
from cam_creation_studio.shared.serialization import from_dict, to_dict

ezdxf_math = pytest.importorskip("ezdxf.math", reason="needs the 'dxf' extra")

MIRRORED = (0.0, 0.0, -1.0)
TILTED = (0.0, 0.6, 0.8)


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeOcsEntity:
    """An ezdxf-shaped entity whose ``ocs()`` is ezdxf's real OCS."""

    def __init__(self, dxftype, extrusion=DEFAULT_EXTRUSION, **dxf):
        self._t = dxftype
        self.dxf = _NS(layer="0", handle="1", extrusion=extrusion, **dxf)
        self._extrusion = extrusion

    def dxftype(self):
        return self._t

    def ocs(self):
        return ezdxf_math.OCS(self._extrusion)


class FakeLwPolyline(FakeOcsEntity):
    def __init__(self, points, elevation=0.0, extrusion=DEFAULT_EXTRUSION,
                 closed=False):
        super().__init__("LWPOLYLINE", extrusion=extrusion, elevation=elevation)
        self._points = points
        self.closed = closed

    def get_points(self, fmt="xyb"):
        return list(self._points)


def codes(diags):
    return [d.code for d in diags]


def circle(extrusion=DEFAULT_EXTRUSION, center=(5, 5, 0), radius=3):
    return FakeOcsEntity("CIRCLE", extrusion=extrusion, center=center, radius=radius)


def arc(extrusion=DEFAULT_EXTRUSION, center=(5, 5, 0), radius=3,
        start_angle=0.0, end_angle=90.0):
    return FakeOcsEntity("ARC", extrusion=extrusion, center=center, radius=radius,
                         start_angle=start_angle, end_angle=end_angle)


# --------------------------------------------------------------------------- #
# Default extrusion must remain untouched
# --------------------------------------------------------------------------- #
def test_default_extrusion_circle_is_coordinate_compatible():
    entity, diags = translate(circle(), scale=1.0)
    assert (entity.center.x, entity.center.y, entity.center.z) == (5.0, 5.0, 0.0)
    assert entity.extrusion is None            # no evidence field when default
    assert diags == []


def test_default_extrusion_arc_keeps_its_angles():
    entity, _ = translate(arc(start_angle=30.0, end_angle=200.0), scale=1.0)
    assert (entity.start_angle, entity.end_angle) == (30.0, 200.0)


def test_absent_extrusion_attribute_is_treated_as_default():
    entity = FakeOcsEntity("CIRCLE", center=(5, 5, 0), radius=3)
    del entity.dxf.extrusion
    result, diags = translate(entity, scale=1.0)
    assert result.center.x == 5.0
    assert diags == []


def test_default_extrusion_lwpolyline_at_zero_elevation_is_unchanged():
    entity, diags = translate(
        FakeLwPolyline([(0, 0, 0), (10, 0, 0), (10, 10, 0)]), scale=1.0)
    assert [(v.x, v.y, v.z) for v in entity.vertices] == [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]
    assert diags == []


# --------------------------------------------------------------------------- #
# Mirrored extrusion (0,0,-1) — exactly representable
# --------------------------------------------------------------------------- #
def test_mirrored_circle_centre_is_corrected():
    entity, diags = translate(circle(extrusion=MIRRORED), scale=1.0)
    assert (entity.center.x, entity.center.y) == (-5.0, 5.0)
    assert diags == []                          # nothing lost, nothing to report


def test_mirrored_extrusion_is_kept_as_evidence():
    entity, _ = translate(circle(extrusion=MIRRORED), scale=1.0)
    assert (entity.extrusion.x, entity.extrusion.y, entity.extrusion.z) == MIRRORED


def test_mirrored_arc_preserves_its_locus():
    """A mirror reverses orientation, and Arc2D is defined CCW.

    Both the locus and the start/end identity cannot survive; we keep the locus,
    which is the geometry. The swept points must match ezdxf's own.
    """
    source = arc(extrusion=MIRRORED, start_angle=0.0, end_angle=90.0)
    entity, _ = translate(source, scale=1.0)

    def point_at(deg):
        t = math.radians(deg)
        return (round(entity.center.x + entity.radius * math.cos(t), 6),
                round(entity.center.y + entity.radius * math.sin(t), 6))

    # ezdxf places the mirrored arc's endpoints at (-8,5) and (-5,8).
    assert sorted([point_at(entity.start_angle), point_at(entity.end_angle)]) == \
        sorted([(-8.0, 5.0), (-5.0, 8.0)])
    # ...and the sweep magnitude is unchanged, not the 270° complement.
    assert (entity.end_angle - entity.start_angle) % 360.0 == 90.0


def test_mirror_angle_helper_is_a_reflection_and_a_swap():
    assert _mirror_arc_angles(0.0, 90.0) == (90.0, 180.0)
    assert _mirror_arc_angles(30.0, 60.0) == (120.0, 150.0)


def test_mirrored_arc_produces_no_diagnostic():
    _, diags = translate(arc(extrusion=MIRRORED), scale=1.0)
    assert diags == []


# --------------------------------------------------------------------------- #
# Tilted extrusion — corrected centre, honest about the plane
# --------------------------------------------------------------------------- #
def test_tilted_circle_reports_the_unrepresentable_plane():
    entity, diags = translate(circle(extrusion=TILTED), scale=1.0)
    assert codes(diags) == [diag.OCS_TRANSFORM_FAILED]
    assert entity is not None                   # centre still corrected
    assert diag.OCS_TRANSFORM_FAILED not in diag.LOSS_CODES


def test_tilted_arc_centre_matches_ezdxf():
    source = arc(extrusion=TILTED, center=(10, 0, 0))
    expected = ezdxf_math.OCS(TILTED).to_wcs((10, 0, 0))
    entity, _ = translate(source, scale=1.0)
    assert entity.center.x == pytest.approx(expected.x)
    assert entity.center.y == pytest.approx(expected.y)


def test_tilted_extrusion_is_not_planar():
    assert _is_planar_extrusion(DEFAULT_EXTRUSION)
    assert _is_planar_extrusion(MIRRORED)
    assert not _is_planar_extrusion(TILTED)


def test_tilted_arc_angles_are_left_alone():
    # The mirror rule applies only to planar ±Z extrusions; inventing an angle
    # transform for a tilted plane would be worse than declaring the limit.
    entity, _ = translate(arc(extrusion=TILTED, start_angle=10.0, end_angle=20.0),
                          scale=1.0)
    assert (entity.start_angle, entity.end_angle) == (10.0, 20.0)


# --------------------------------------------------------------------------- #
# LWPOLYLINE elevation
# --------------------------------------------------------------------------- #
def test_elevation_becomes_the_wcs_z():
    entity, diags = translate(
        FakeLwPolyline([(0, 0, 0), (10, 0, 0)], elevation=25.0), scale=1.0)
    assert [v.z for v in entity.vertices] == [25.0, 25.0]
    assert diags == []
    assert diag.LWPOLYLINE_ELEVATION_DROPPED not in codes(diags)


def test_elevation_is_scaled_with_the_drawing_units():
    entity, _ = translate(
        FakeLwPolyline([(0, 0, 0)], elevation=1.0), scale=25.4)
    assert entity.vertices[0].z == pytest.approx(25.4)


def test_elevated_bulged_closed_lwpolyline_keeps_everything():
    entity, diags = translate(
        FakeLwPolyline([(0, 0, 0.5), (10, 0, 0), (10, 10, 0)],
                       elevation=25.0, closed=True),
        scale=1.0)
    assert entity.closed is True
    assert [v.z for v in entity.vertices] == [25.0] * 3
    assert diag.POLYLINE_BULGE_IGNORED in codes(diags)   # bulge still reported
    assert [(v.x, v.y) for v in entity.vertices] == [(0, 0), (10, 0), (10, 10)]


def test_vertex_order_is_preserved():
    pts = [(0, 0, 0), (3, 1, 0), (7, 4, 0), (9, 2, 0)]
    entity, _ = translate(FakeLwPolyline(pts, elevation=2.0), scale=1.0)
    assert [(v.x, v.y) for v in entity.vertices] == [(p[0], p[1]) for p in pts]


def test_elevated_lwpolyline_with_mirrored_extrusion_transforms_xy_too():
    entity, _ = translate(
        FakeLwPolyline([(5, 5, 0)], elevation=3.0, extrusion=MIRRORED), scale=1.0)
    expected = ezdxf_math.OCS(MIRRORED).to_wcs((5, 5, 3))
    v = entity.vertices[0]
    assert (v.x, v.y, v.z) == pytest.approx((expected.x, expected.y, expected.z))


def test_lwpolyline_coordinates_are_plain_floats():
    entity, _ = translate(
        FakeLwPolyline([(0, 0, 0), (1, 1, 0)], elevation=4.0), scale=1.0)
    for v in entity.vertices:
        assert type(v.x) is float and type(v.y) is float and type(v.z) is float


# --------------------------------------------------------------------------- #
# Bounds and serialization
# --------------------------------------------------------------------------- #
def test_bounds_follow_the_corrected_placement():
    default_c, _ = translate(circle(), scale=1.0)
    mirrored_c, _ = translate(circle(extrusion=MIRRORED), scale=1.0)
    assert (default_c.bounds.min_x, default_c.bounds.max_x) == (2.0, 8.0)
    assert (mirrored_c.bounds.min_x, mirrored_c.bounds.max_x) == (-8.0, -2.0)


def test_elevation_alone_does_not_change_planar_bounds():
    flat, _ = translate(FakeLwPolyline([(0, 0, 0), (10, 10, 0)]), scale=1.0)
    high, _ = translate(FakeLwPolyline([(0, 0, 0), (10, 10, 0)], elevation=99.0),
                        scale=1.0)
    assert (flat.bounds.min_x, flat.bounds.min_y, flat.bounds.max_x, flat.bounds.max_y) == \
           (high.bounds.min_x, high.bounds.min_y, high.bounds.max_x, high.bounds.max_y)


@pytest.mark.parametrize("build", [
    lambda: translate(circle(extrusion=MIRRORED), scale=1.0)[0],
    lambda: translate(arc(extrusion=MIRRORED), scale=1.0)[0],
    lambda: translate(FakeLwPolyline([(0, 0, 0), (1, 1, 0)], elevation=5.0,
                                     extrusion=MIRRORED), scale=1.0)[0],
])
def test_corrected_entities_round_trip_through_the_serializer(build):
    entity = build()
    klass = {"circle": Circle2D, "arc": Arc2D, "polyline": Polyline2D}[entity.kind]
    assert from_dict(klass, to_dict(entity)) == entity


def test_non_ocs_entities_are_never_transformed():
    """LINE and SPLINE coordinates are WCS in DXF; touching them would corrupt."""
    line = FakeOcsEntity("LINE", extrusion=MIRRORED,
                         start=(1, 2, 0), end=(3, 4, 0))
    entity, _ = translate(line, scale=1.0)
    assert (entity.start.x, entity.start.y) == (1.0, 2.0)
    assert (entity.end.x, entity.end.y) == (3.0, 4.0)
