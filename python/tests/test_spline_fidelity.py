"""Spline representation fidelity (CS-008 remediation, PR 2).

The importer now keeps a spline the way the source described it — control points
or fit points — rather than assuming one form and reporting the other as broken.

The governing rule under test: **a loss diagnostic describes actual information
loss, never merely the presence of a non-default DXF feature.** A fit-point
spline is faithfully preserved and therefore silent. Weights that survive are
silent. Only genuinely unpreservable semantics earn a finding.

These use the duck-typed `translate()` entry point rather than DXF fixtures,
because the interesting cases here are malformed files that ezdxf's own
validation makes awkward to author.
"""

import pytest

from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.entities import translate
from cam_creation_studio.geometry.models import (
    REPRESENTATION_CONTROL,
    REPRESENTATION_FIT,
    Spline2D,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.shared.serialization import from_dict, to_dict


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def hasattr(self, name):          # mirrors ezdxf's DXF namespace probe
        return name in self.__dict__


class FakeSpline:
    """An ezdxf-shaped SPLINE stand-in; `translate()` only duck-types."""

    def __init__(self, *, control_points=(), fit_points=(), weights=(), knots=(),
                 degree=3, flags=0, closed=False, **dxf):
        self.dxf = _NS(degree=degree, flags=flags, layer="0", handle="1", **dxf)
        self.control_points = list(control_points)
        self.fit_points = list(fit_points)
        self.weights = list(weights)
        self.knots = list(knots)
        self.closed = closed

    def dxftype(self):
        return "SPLINE"


P = [Point(0, 0), Point(1, 2), Point(2, 0), Point(3, 2)]


def codes(diags):
    return [d.code for d in diags]


# --------------------------------------------------------------------------- #
# Representation
# --------------------------------------------------------------------------- #
def test_control_point_spline_is_control_representation():
    entity, diags = translate(FakeSpline(control_points=P), scale=1.0)
    assert entity.representation == REPRESENTATION_CONTROL
    assert entity.defining_points == entity.control_points
    assert diags == []


def test_fit_point_spline_is_fit_representation_and_silent():
    entity, diags = translate(FakeSpline(fit_points=P), scale=1.0)
    assert entity.representation == REPRESENTATION_FIT
    assert entity.defining_points == entity.fit_points
    assert diags == []                     # faithfully preserved => no finding


def test_control_points_win_when_both_are_present():
    # Control points define the curve exactly; fit points are the authoring
    # intent the CAD tool fitted them to. Both are kept.
    entity, _ = translate(
        FakeSpline(control_points=P, fit_points=[Point(9, 9)]), scale=1.0)
    assert entity.representation == REPRESENTATION_CONTROL
    assert len(entity.fit_points) == 1     # retained, just not authoritative


def test_fit_spline_bounds_come_from_fit_points():
    entity, _ = translate(FakeSpline(fit_points=P), scale=1.0)
    assert entity.bounds.max_x == 3.0
    assert entity.bounds.max_y == 2.0


def test_points_are_scaled_but_knots_and_weights_are_not():
    """Knots are parameter space and weights are dimensionless."""
    entity, _ = translate(
        FakeSpline(control_points=P, weights=[1, 4, 4, 1], knots=[0, 0, 0.5, 1]),
        scale=25.4,                         # inches -> mm
    )
    assert entity.control_points[-1].x == pytest.approx(3 * 25.4)
    assert entity.weights == [1.0, 4.0, 4.0, 1.0]
    assert entity.knots == [0.0, 0.0, 0.5, 1.0]


def test_flags_are_decoded():
    entity, _ = translate(
        FakeSpline(control_points=P, flags=1 | 2 | 4, weights=[1, 1, 1, 1]),
        scale=1.0)
    assert entity.closed and entity.periodic and entity.rational


def test_weights_alone_mark_a_spline_rational():
    entity, _ = translate(
        FakeSpline(control_points=P, weights=[1, 2, 2, 1], flags=0), scale=1.0)
    assert entity.rational is True


# --------------------------------------------------------------------------- #
# Genuine loss — and only genuine loss
# --------------------------------------------------------------------------- #
def test_spline_with_no_points_is_excluded_not_admitted_empty():
    entity, diags = translate(FakeSpline(), scale=1.0)
    assert entity is None                  # never enters the collection
    assert codes(diags) == [diag.EMPTY_SPLINE_GEOMETRY]
    assert diags[0].recoverable is False
    assert diags[0].is_loss


def test_mismatched_weights_are_dropped_and_reported():
    # weight[i] belongs to control_points[i]; a count mismatch makes that
    # mapping unrecoverable, so the weights cannot be preserved.
    entity, diags = translate(
        FakeSpline(control_points=P, weights=[1.0, 2.0]), scale=1.0)
    assert codes(diags) == [diag.RATIONAL_SPLINE_WEIGHTS_DROPPED]
    assert entity.weights == []
    assert diags[0].metadata == {
        "weight_count": 2, "control_point_count": 4, "degree": 3}


def test_matched_weights_produce_no_finding():
    _, diags = translate(
        FakeSpline(control_points=P, weights=[1, 1, 1, 1]), scale=1.0)
    assert diags == []


def test_fit_spline_with_tangents_reports_the_unrepresented_constraint():
    # Tangents shape a fitted curve; the fit points alone under-determine it.
    entity, diags = translate(
        FakeSpline(fit_points=P, start_tangent=(1, 0, 0)), scale=1.0)
    assert codes(diags) == [diag.FIT_POINT_SPLINE_UNREPRESENTED]
    assert entity.representation == REPRESENTATION_FIT
    assert len(entity.fit_points) == 4     # the points themselves are kept
    assert diags[0].metadata["tangents"] == ["start_tangent"]


def test_both_tangents_are_named():
    _, diags = translate(
        FakeSpline(fit_points=P, start_tangent=(1, 0, 0), end_tangent=(0, 1, 0)),
        scale=1.0)
    assert diags[0].metadata["tangents"] == ["start_tangent", "end_tangent"]


def test_tangents_on_a_control_point_spline_are_not_reported():
    # Control points define the curve outright; tangents add nothing to lose.
    _, diags = translate(
        FakeSpline(control_points=P, start_tangent=(1, 0, 0)), scale=1.0)
    assert diag.FIT_POINT_SPLINE_UNREPRESENTED not in codes(diags)


def test_under_specified_control_spline_is_advisory_not_loss():
    # Every point given was preserved, so nothing was lost — it is the source
    # that is short of points for its declared degree.
    _, diags = translate(
        FakeSpline(control_points=P[:2], degree=3), scale=1.0)
    assert codes(diags) == [diag.INVALID_SPLINE]
    assert diags[0].is_loss is False


def test_fit_spline_is_never_judged_against_control_point_count():
    # The old rule flagged any spline with fewer than degree+1 control points;
    # a fit spline legitimately has none.
    _, diags = translate(FakeSpline(fit_points=P[:2], degree=3), scale=1.0)
    assert diag.INVALID_SPLINE not in codes(diags)


# --------------------------------------------------------------------------- #
# Model invariant
# --------------------------------------------------------------------------- #
def test_empty_spline_cannot_be_constructed():
    with pytest.raises(ValueError, match="empty spline"):
        Spline2D()


def test_representation_must_match_the_points_carried():
    with pytest.raises(ValueError, match="no fit points"):
        Spline2D(control_points=P, representation=REPRESENTATION_FIT)
    with pytest.raises(ValueError, match="no control points"):
        Spline2D(fit_points=P, representation=REPRESENTATION_CONTROL)


def test_unknown_representation_is_rejected():
    with pytest.raises(ValueError, match="representation must be"):
        Spline2D(control_points=P, representation="nurbs")


def test_spline_round_trips_through_the_shared_serializer():
    original = Spline2D(
        control_points=P, knots=[0.0, 0.5, 1.0], weights=[1.0, 2.0, 2.0, 1.0],
        degree=3, closed=True, periodic=True, rational=True, layer="curves")
    assert from_dict(Spline2D, to_dict(original)) == original


def test_fit_spline_round_trips_through_the_shared_serializer():
    original = Spline2D(fit_points=P, representation=REPRESENTATION_FIT)
    assert from_dict(Spline2D, to_dict(original)) == original


def test_legacy_serialized_spline_still_loads():
    # Documents printed before PR 2 carry only control points and degree; the
    # additive fields default and the representation resolves to "control".
    legacy = {"kind": "spline", "degree": 3, "closed": False, "layer": "0",
              "control_points": [{"x": 0.0, "y": 0.0, "z": 0.0},
                                 {"x": 1.0, "y": 1.0, "z": 0.0}]}
    restored = from_dict(Spline2D, legacy)
    assert restored.representation == REPRESENTATION_CONTROL
    assert restored.fit_points == []
    assert restored.weights == []
