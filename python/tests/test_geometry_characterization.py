"""Characterization of DXF import fidelity against the golden corpus (CS-008).

This module began as the before-half of a before-and-after regression pair: it
pinned what the importer did when the CS-008 fidelity defects were live, so the
remediation increments had to change it deliberately and visibly rather than
quietly moving geometry underneath a green suite.

    PR 1 — record the defects, change nothing                     [done]
    PR 2 — spline fidelity        → flipped the spline tests      [done]
    PR 3 — coordinate correctness → flipped the OCS/elevation ones [done]

All three have landed, so every assertion here now describes **correct**
behavior and guards it against regression. Each flipped test keeps its original
subject in the docstring ("Was: ...") so the history stays readable — and the
OCS cases still compare against the same ezdxf reference the defect versions
used, with the `!=` that documented the bug now the `==` that protects the fix.

The corpus lives in ``tests/fixtures/`` and is immutable — see
``fixtures/MAKE_FIXTURES.py``.
"""

import os

import pytest

from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.importer import import_dxf

ezdxf = pytest.importorskip("ezdxf", reason="DXF import requires the 'dxf' extra")

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return import_dxf(os.path.join(FIXTURES, name))


def codes(collection):
    return [d.code for d in collection.diagnostics]


def reference_wcs(name, dxftype):
    """The true WCS point per ezdxf's own OCS helper — the target for PR 3."""
    doc = ezdxf.readfile(os.path.join(FIXTURES, name))
    entity = doc.modelspace().query(dxftype)[0]
    return tuple(entity.ocs().to_wcs(entity.dxf.center))


# --------------------------------------------------------------------------- #
# Corpus integrity
# --------------------------------------------------------------------------- #
FIXTURE_NAMES = (
    "extruded_circle.dxf",
    "fit_spline.dxf",
    "lwpolyline_elevated.dxf",
    "ocs_arc.dxf",
    "polyline_elevated.dxf",
    "unsupported_entity.dxf",
    "weighted_spline.dxf",
)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_fixture_imports_without_raising(name):
    assert load(name) is not None


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_import_is_deterministic(name):
    assert load(name).to_dict() == load(name).to_dict()


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_fixture_declares_millimetres(name):
    assert load(name).metadata.source_units == "mm"
    assert load(name).metadata.unit_scale == 1.0


# --------------------------------------------------------------------------- #
# FIXED in PR 3 — coordinate correctness
# --------------------------------------------------------------------------- #
# Flipped from the defect assertions, keeping the same ezdxf OCS reference: the
# `!=` that documented the bug is now the `==` that guards the fix.
def test_extruded_circle_imports_at_true_wcs_coordinates():
    """Was: imported at (+5,5), mirrored, silently.

    Extrusion (0,0,-1) mirrors OCS X. The circle is drawn at OCS (5,5) and its
    true WCS centre is (-5,5), which is now where it lands.
    """
    circle = load("extruded_circle.dxf").of_kind("circle")[0]
    expected_x, expected_y, _ = reference_wcs("extruded_circle.dxf", "CIRCLE")

    assert expected_x == -5.0                       # ezdxf's reference
    assert circle.center.x == expected_x            # was `!=`
    assert circle.center.y == expected_y


def test_ocs_arc_centre_is_transformed_by_the_arbitrary_axis_algorithm():
    """Was: no transform applied at all.

    A tilted extrusion (0, 0.6, 0.8) exercises the general OCS case rather than
    the degenerate mirror.
    """
    arc = load("ocs_arc.dxf").of_kind("arc")[0]
    expected_x, _, _ = reference_wcs("ocs_arc.dxf", "ARC")

    assert expected_x == -10.0
    assert arc.center.x == expected_x                # was `!=`


def test_planar_ocs_correction_is_silent_because_nothing_is_lost():
    """A successful transform is correct behavior, not a finding.

    The mirrored circle stays parallel to WCS XY, so the planar model holds it
    exactly and there is nothing to report.
    """
    assert codes(load("extruded_circle.dxf")) == []


def test_tilted_extrusion_reports_the_unrepresentable_plane():
    """Was: silent. Now the one OCS case that genuinely cannot be represented.

    An extrusion of (0, 0.6, 0.8) tilts the arc out of the XY plane entirely —
    its endpoint has a non-zero WCS Z. The centre is corrected, but a planar
    Arc2D cannot express the plane, so the importer says so instead of returning
    a confidently flat answer.
    """
    collection = load("ocs_arc.dxf")
    assert diag.OCS_TRANSFORM_FAILED in codes(collection)
    assert collection.report().loss_count == 0      # a limit, not lost data


def test_ocs_entities_retain_their_source_extrusion_as_evidence():
    circle = load("extruded_circle.dxf").of_kind("circle")[0]
    arc = load("ocs_arc.dxf").of_kind("arc")[0]

    assert (circle.extrusion.x, circle.extrusion.y, circle.extrusion.z) == (0.0, 0.0, -1.0)
    assert (arc.extrusion.x, arc.extrusion.y, arc.extrusion.z) == (0.0, 0.6, 0.8)


def test_corrected_coordinates_move_the_planar_bounds():
    """The mirror is visible in the bounds, not just the centre."""
    bounds = load("extruded_circle.dxf").bounds
    assert (bounds.min_x, bounds.max_x) == (-8.0, -2.0)   # was (2.0, 8.0)
    assert (bounds.min_y, bounds.max_y) == (2.0, 8.0)     # unchanged by an X mirror


def test_lwpolyline_elevation_is_preserved():
    """Was: elevation 25 flattened to 0, silently."""
    collection = load("lwpolyline_elevated.dxf")
    polyline = collection.of_kind("polyline")[0]

    assert [v.z for v in polyline.vertices] == [25.0] * 4
    assert codes(collection) == []                  # preserved => nothing to report
    assert diag.LWPOLYLINE_ELEVATION_DROPPED not in codes(collection)


def test_polyline_paths_now_agree_on_elevation():
    """Was: fidelity depended on which DXF entity the authoring tool emitted."""
    lw = load("lwpolyline_elevated.dxf").of_kind("polyline")[0]
    pl = load("polyline_elevated.dxf").of_kind("polyline")[0]

    assert [v.z for v in lw.vertices] == [v.z for v in pl.vertices]
    assert {v.z for v in lw.vertices} == {25.0}


def test_elevation_does_not_alter_the_planar_bounds_contract():
    """Z is preserved on points; XY bounds stay XY. No 3D bounds were introduced."""
    lw = load("lwpolyline_elevated.dxf").bounds
    pl = load("polyline_elevated.dxf").bounds

    assert (lw.min_x, lw.min_y, lw.max_x, lw.max_y) == (0.0, 0.0, 10.0, 10.0)
    assert (lw.min_x, lw.min_y, lw.max_x, lw.max_y) == (pl.min_x, pl.min_y, pl.max_x, pl.max_y)


def test_polyline_elevation_is_preserved_and_must_stay_that_way():
    """The half that was always correct — PR 3 must not have regressed it."""
    polyline = load("polyline_elevated.dxf").of_kind("polyline")[0]
    assert [v.z for v in polyline.vertices] == [25.0] * 4
    assert polyline.closed is True


# --------------------------------------------------------------------------- #
# FIXED in PR 2 — spline fidelity
# --------------------------------------------------------------------------- #
# These previously asserted the defects. PR 2 flipped them, which is the whole
# point of the characterization pair; they now guard the fix against regression.
def test_fit_point_spline_is_preserved_as_fit_representation():
    """Was: imported as an empty entity with zero control points.

    Now the fit points are kept and the entity says so, instead of pretending to
    be a control-point spline that lost its points.
    """
    collection = load("fit_spline.dxf")
    spline = collection.of_kind("spline")[0]

    assert spline.representation == "fit"
    assert len(spline.fit_points) == 4
    assert spline.control_points == []              # correct: none were given
    assert spline.defining_points == spline.fit_points
    assert spline.bounds is not None                # contributes real extent now
    assert collection.bounds is not None


def test_fit_point_spline_is_no_longer_flagged_as_invalid():
    """Was: INVALID_SPLINE, because zero control points looked degenerate.

    A fit-point spline is a complete description, not a broken control-point one,
    so there is nothing to report.
    """
    assert diag.INVALID_SPLINE not in codes(load("fit_spline.dxf"))
    assert codes(load("fit_spline.dxf")) == []


def test_rational_spline_weights_are_preserved():
    """Was: weights [1,4,4,1] discarded silently."""
    spline = load("weighted_spline.dxf").of_kind("spline")[0]

    assert spline.weights == [1.0, 4.0, 4.0, 1.0]
    assert spline.rational is True
    assert len(spline.knots) == 8                   # knot vector kept too
    assert spline.representation == "control"


def test_faithfully_imported_splines_record_no_loss():
    """Still zero — but now because nothing was lost, not because nothing looked.

    This is the refinement that matters: a loss diagnostic describes actual
    information loss, never merely the presence of a non-default DXF feature.
    """
    for name in ("weighted_spline.dxf", "fit_spline.dxf"):
        report = load(name).report()
        assert report.loss_count == 0
        assert not report.has_loss


def test_knots_and_weights_are_not_scaled_by_drawing_units():
    """Knots are parameter space and weights are dimensionless.

    Both fixtures are millimetre drawings (scale 1.0), so this pins the intent
    rather than catching a live bug — the unit test in `test_spline_fidelity`
    exercises a non-unity scale.
    """
    spline = load("weighted_spline.dxf").of_kind("spline")[0]
    assert spline.weights == [1.0, 4.0, 4.0, 1.0]
    assert max(spline.knots) == 1.0                 # normalized knot vector


# --------------------------------------------------------------------------- #
# Behavior that is already correct
# --------------------------------------------------------------------------- #
def test_unsupported_entity_is_reported_and_survivors_are_kept():
    collection = load("unsupported_entity.dxf")

    assert diag.UNSUPPORTED_ENTITY in codes(collection)
    assert collection.metadata.raw_entity_count == 2
    assert collection.metadata.entity_count == 1
    assert collection.metadata.unsupported_entity_count == 1
    assert collection.metadata.has_lossy_import is True
    assert len(collection.of_kind("line")) == 1     # the ELLIPSE took nothing with it


def test_unsupported_entity_counts_as_loss_in_the_report():
    # The one fidelity failure the existing importer already accounts for.
    report = load("unsupported_entity.dxf").report()
    assert report.loss_count == 1
    assert report.has_loss


def test_reports_round_trip_for_every_fixture():
    for name in FIXTURE_NAMES:
        collection = load(name)
        assert collection.report() == collection.report()
        collection.to_json()                        # must stay JSON-encodable


def test_lwpolyline_coordinates_are_plain_floats():
    """Was: numpy scalars, because this path skipped the `float()` coercion every
    other path applies. PR 3 rewrote it and coerced, as flagged."""
    for name in ("lwpolyline_elevated.dxf", "polyline_elevated.dxf"):
        for vertex in load(name).of_kind("polyline")[0].vertices:
            assert type(vertex.x) is float
            assert type(vertex.y) is float
            assert type(vertex.z) is float
