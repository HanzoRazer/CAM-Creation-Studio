"""Characterization of DXF import fidelity against the golden corpus (CS-008).

**These tests pin current behavior, including behavior that is wrong.**

They are the before-half of a before-and-after regression pair. Tests named
``test_defect_*`` assert what the importer does *today* so that the two
remediation increments which follow have to change them deliberately and
visibly, rather than quietly moving geometry underneath a green suite.

    PR 1 — record the defects, change nothing            [done]
    PR 2 — spline fidelity        → flipped the spline tests   [done]
    PR 3 — coordinate correctness → flips the OCS and elevation tests

A ``test_defect_*`` failing after those increments is the *intended* signal, not
a regression. Each one names its target in the docstring. Everything else in
this module characterizes behavior that is already correct and must survive both
increments unchanged.

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
# DEFECT — coordinate correctness (PR 3 target)
# --------------------------------------------------------------------------- #
def test_defect_extruded_circle_imports_at_mirrored_coordinates():
    """PR 3 target. Extrusion (0,0,-1) mirrors OCS X; the importer ignores it.

    The circle is drawn at OCS (5,5). Its true WCS centre is (-5,5). We import
    it at (+5,5) — not lost metadata, a *wrong position*, and a part machined
    from this would be mirrored.
    """
    circle = load("extruded_circle.dxf").of_kind("circle")[0]
    expected_x, expected_y, _ = reference_wcs("extruded_circle.dxf", "CIRCLE")

    assert expected_x == -5.0                       # ezdxf agrees on the truth
    assert circle.center.x == 5.0                   # ...and we disagree with it
    assert circle.center.x != expected_x            # PR 3 flips this to ==
    assert circle.center.y == expected_y            # Y happens to be unaffected


def test_defect_ocs_arc_imports_at_untransformed_coordinates():
    """PR 3 target. A tilted extrusion (0, 0.6, 0.8) needs the arbitrary-axis
    algorithm; the importer applies no transform at all."""
    arc = load("ocs_arc.dxf").of_kind("arc")[0]
    expected_x, _, _ = reference_wcs("ocs_arc.dxf", "ARC")

    assert expected_x == -10.0
    assert arc.center.x == 10.0
    assert arc.center.x != expected_x               # PR 3 flips this to ==


def test_defect_ocs_entities_produce_no_diagnostic():
    """PR 3 target. Silent is the problem: neither file yields any finding."""
    assert codes(load("extruded_circle.dxf")) == []
    assert codes(load("ocs_arc.dxf")) == []


def test_defect_lwpolyline_elevation_is_dropped_silently():
    """PR 3 target. `get_points("xyb")` never reads `dxf.elevation`, so Z=25
    becomes Z=0 with no diagnostic."""
    collection = load("lwpolyline_elevated.dxf")
    polyline = collection.of_kind("polyline")[0]

    assert [v.z for v in polyline.vertices] == [0.0, 0.0, 0.0, 0.0]  # source said 25
    assert codes(collection) == []
    assert diag.LWPOLYLINE_ELEVATION_DROPPED not in codes(collection)


def test_defect_polyline_paths_disagree_on_elevation():
    """PR 3 target. The same shape at the same Z survives or is flattened purely
    according to which DXF entity the authoring tool emitted."""
    lw = load("lwpolyline_elevated.dxf").of_kind("polyline")[0]
    pl = load("polyline_elevated.dxf").of_kind("polyline")[0]

    assert {v.z for v in pl.vertices} == {25.0}     # POLYLINE keeps Z
    assert {v.z for v in lw.vertices} == {0.0}      # LWPOLYLINE loses it
    assert [v.z for v in lw.vertices] != [v.z for v in pl.vertices]


def test_polyline_elevation_is_preserved_and_must_stay_that_way():
    """Not a defect — the correct half of the pair. PR 3 must not regress it."""
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


def test_lwpolyline_coordinates_are_numpy_backed():
    """An observation, not a defect. `get_points()` returns numpy scalars and the
    LWPOLYLINE path skips the `float()` coercion every other path applies.

    Harmless today — `np.float64` subclasses `float`, so JSON and arithmetic both
    work — but PR 3 rewrites this path and should coerce for consistency.
    """
    vertex = load("lwpolyline_elevated.dxf").of_kind("polyline")[0].vertices[0]
    assert isinstance(vertex.x, float)              # true via subclassing
    assert type(vertex.x) is not float              # ...but not the plain builtin
