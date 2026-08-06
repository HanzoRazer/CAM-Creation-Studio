"""Characterization of DXF import fidelity against the golden corpus (CS-008).

**These tests pin current behavior, including behavior that is wrong.**

They are the before-half of a before-and-after regression pair. Tests named
``test_defect_*`` assert what the importer does *today* so that the two
remediation increments which follow have to change them deliberately and
visibly, rather than quietly moving geometry underneath a green suite.

    PR 1 (this one) — record the defects, change nothing
    PR 2            — spline fidelity        → flips the spline defect tests
    PR 3            — coordinate correctness → flips the OCS and elevation tests

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
# DEFECT — spline fidelity (PR 2 target)
# --------------------------------------------------------------------------- #
def test_defect_fit_point_spline_becomes_an_empty_entity():
    """PR 2 target. A fit-point spline yields a `Spline2D` with zero control
    points: an entity that exists, claims to be geometry, and contains none."""
    collection = load("fit_spline.dxf")
    spline = collection.of_kind("spline")[0]

    assert spline.control_points == []
    assert spline.bounds is None                    # contributes nothing
    assert collection.bounds is None                # ...and nothing to the file
    assert collection.metadata.entity_count == 1    # yet counts as imported


def test_fit_point_spline_is_at_least_flagged():
    """Not silent — INVALID_SPLINE fires. PR 2 replaces it with a code that says
    what was lost, so this assertion is expected to change."""
    assert diag.INVALID_SPLINE in codes(load("fit_spline.dxf"))


def test_defect_rational_spline_weights_are_dropped_silently():
    """PR 2 target. Weights [1,4,4,1] make this a genuinely different curve from
    the same control points unweighted. Nothing records their loss."""
    collection = load("weighted_spline.dxf")
    spline = collection.of_kind("spline")[0]

    assert len(spline.control_points) == 4
    assert not hasattr(spline, "weights")           # PR 2 adds the field
    assert codes(collection) == []                  # PR 2 adds the diagnostic
    assert diag.RATIONAL_SPLINE_WEIGHTS_DROPPED not in codes(collection)


def test_defect_no_spline_loss_is_recorded_as_loss():
    """PR 2 target. `report()` reports a clean import for both spline fixtures,
    because nothing marks the missing weights or fit points as a cost."""
    assert load("weighted_spline.dxf").report().loss_count == 0
    assert load("fit_spline.dxf").report().loss_count == 0


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
