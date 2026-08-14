"""CS-008R closure regression matrix — every audit finding, re-probed at once.

This file is deliberately **not** a second copy of the specialised suites. Each
finding already has a detailed home (``test_geometry_ocs.py``,
``test_spline_fidelity.py``, ``test_geometry_elevation.py``,
``test_geometry_provenance.py``, ``test_geometry_layers.py``), and those remain
authoritative for detail. What did not exist before is a single place that proves
all ten findings hold *simultaneously* against one commit.

That distinction is the point. The remediations landed in five separate PRs over
five days, each green on its own branch. Green-in-isolation is not the same claim
as green-together, and the closure standard in ``docs/dev_orders/LEDGER.md``
requires the second one:

    A remediation is not self-certifying. The closure audit re-probes rather than
    reading the ledger back to itself.

So every assertion here is a *re-probe*, phrased as the invariant the finding
asked for, not as "the fix is still installed".

Two findings are characterisations rather than fixes, and are marked as such:

* **F9** is an accepted limitation. Its test pins the accepted behaviour so that a
  future change to it becomes visible rather than silent. It asserts the contracts
  that must hold, *not* that the type is numpy — that would freeze the defect in
  place and make the eventual cleanup look like a regression.
* **F8** is a documentation finding; only its machine-checkable half lives here.

Parent artifact: ``docs/audits/CS-008_REAUDIT.md``.
Closure report: ``docs/audits/CS-008R_CLOSURE.md``.
"""

from __future__ import annotations

import json
import math
import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry.models import GeometryCollection  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    return import_dxf(os.path.join(FIXTURES, name))


def _of_kind(collection, kind):
    return [e for e in collection.entities if e.kind == kind]


# --------------------------------------------------------------------------
# F1 — OCS/extrusion resolved to WCS
# --------------------------------------------------------------------------

def test_f1_flipped_extrusion_lands_in_world_coordinates():
    """A flipped extrusion mirrors OCS X: the centre is at -5, not +5.

    This is the finding's whole substance. Reading the raw OCS centre is not a
    metadata loss, it is a circle in the wrong place — so the assertion is on the
    coordinate, not on the presence of a transform.
    """
    circle = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    assert circle.center.x == pytest.approx(-5.0)
    assert circle.center.y == pytest.approx(5.0)


def test_f1_tilted_extrusion_is_resolved_and_its_lost_plane_is_reported():
    """A tilted plane resolves *and* says the orientation did not survive.

    Both halves matter. Resolving silently would repeat the original defect in a
    quieter form: the coordinates are right, but a tilted circle read back as a
    flat Circle2D is not the circle that was drawn.
    """
    collection = _load("ocs_arc.dxf")
    assert _of_kind(collection, "arc")
    codes = {d.code for d in collection.diagnostics}
    assert diag.NON_PLANAR_GEOMETRY in codes
    assert diag.OCS_TRANSFORM_FAILED not in codes, (
        "the transform succeeded; a failure code here would state a false reason")


# --------------------------------------------------------------------------
# F2 — fit-point spline yields usable geometry
# --------------------------------------------------------------------------

def test_f2_fit_spline_is_usable_geometry_not_an_empty_shell():
    spline = _of_kind(_load("fit_spline.dxf"), "spline")[0]
    assert spline.representation == "fit"
    assert len(spline.fit_points) >= 2
    assert spline.bounds is not None or spline.fit_points


# --------------------------------------------------------------------------
# F3 / F4 — rational weights and knot vectors survive, unscaled
# --------------------------------------------------------------------------

def test_f3_rational_weights_survive_in_order():
    spline = _of_kind(_load("weighted_spline.dxf"), "spline")[0]
    assert spline.rational is True
    assert spline.weights == [1.0, 4.0, 4.0, 1.0]
    assert len(spline.weights) == len(spline.control_points)


def test_f4_knots_survive_and_are_not_unit_scaled():
    """Knots are parameter space; weights are dimensionless. Neither is a length.

    Scaling either would corrupt the curve while leaving every coordinate looking
    plausible, which is why this is asserted at closure rather than trusted.
    """
    spline = _of_kind(_load("weighted_spline.dxf"), "spline")[0]
    assert spline.knots, "knot vector must survive import"
    assert spline.degree == 3
    assert max(spline.knots) <= 1.0 + 1e-9, (
        "knots outside the unit interval suggest they were scaled with the units")


# --------------------------------------------------------------------------
# F5 — elevation, both 2D polyline paths alike
# --------------------------------------------------------------------------

def test_f5_both_two_dimensional_polyline_paths_agree_on_elevation():
    """The paired control that replaces the withdrawn asymmetry claim.

    ``lwpolyline_elevation`` and ``polyline2d_elevation`` author the same square at
    the same height through the two different DXF representations. Equivalent
    input must produce equivalent geometry; anything else is the import path
    inventing a difference.
    """
    lw = _of_kind(_load("lwpolyline_elevation.dxf"), "polyline")[0]
    p2 = _of_kind(_load("polyline2d_elevation.dxf"), "polyline")[0]

    assert all(v.z == pytest.approx(25.0) for v in lw.vertices)
    assert all(v.z == pytest.approx(25.0) for v in p2.vertices)
    assert [(v.x, v.y, v.z) for v in lw.vertices] == pytest.approx(
        [(v.x, v.y, v.z) for v in p2.vertices])


# --------------------------------------------------------------------------
# F6 — provenance
# --------------------------------------------------------------------------

def test_f6_provenance_answers_where_did_i_come_from():
    entity = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    assert entity.source is not None
    assert entity.source.entity_type == "CIRCLE"
    assert entity.source.handle
    assert entity.source.layer is not None
    assert entity.source.ordinal is not None


def test_f6_provenance_does_not_leak_into_geometric_equality():
    """Two identical shapes compare equal whether or not they share a handle."""
    a = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    b = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    assert a == b
    assert a.source.handle == b.source.handle
    relocated = type(a)(center=a.center, radius=a.radius, layer=a.layer)
    assert relocated == a, "equality must ignore the absent source reference"


# --------------------------------------------------------------------------
# F7 — layer evidence
# --------------------------------------------------------------------------

def test_f7_omitted_layer_is_valid_layer_zero_and_stays_silent(tmp_path):
    """In DXF an omitted layer group code *means* layer 0 — a valid state.

    Flagging it would fire on ordinary valid files, so the absence of a diagnostic
    is the assertion, not an oversight.
    """
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_line((0, 0), (10, 0))
    path = str(tmp_path / "no_layer.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    assert collection.entities[0].layer == "0"
    assert diag.MISSING_LAYER not in {d.code for d in collection.diagnostics}


def test_f7_empty_layer_name_is_reported_and_geometry_is_kept(tmp_path):
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": ""})
    path = str(tmp_path / "empty_layer.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    assert diag.MISSING_LAYER in {d.code for d in collection.diagnostics}
    assert collection.entities, "evidence of a bad layer must not cost the geometry"


# --------------------------------------------------------------------------
# F8 — the machine-checkable half of the documentation finding
# --------------------------------------------------------------------------

def test_f8_reserved_vocabulary_is_registered_but_never_emitted():
    """``LWPOLYLINE_ELEVATION_DROPPED`` is RESERVED: registered, unreachable.

    Retiring it was considered and refused — it is public vocabulary with unknown
    external consumers. The classification is only honest while nothing emits it,
    so that is what this pins. If a future change makes it fire, this test fails
    and the closure report's claim is re-opened rather than quietly falsified.
    """
    assert diag.LWPOLYLINE_ELEVATION_DROPPED in diag.CANONICAL_CODES

    corpus = [f for f in os.listdir(FIXTURES) if f.endswith(".dxf")]
    assert corpus, "the reachability claim is vacuous without fixtures"
    for name in corpus:
        emitted = {d.code for d in _load(name).diagnostics}
        assert diag.LWPOLYLINE_ELEVATION_DROPPED not in emitted, (
            f"{name} emitted a code documented as unreachable")


# --------------------------------------------------------------------------
# F9 — accepted limitation, pinned by contract rather than by type
# --------------------------------------------------------------------------

def test_f9_lwpolyline_coordinates_honour_every_numeric_contract(tmp_path):
    """F9 is accepted: the LWPOLYLINE path yields a ``float`` *subclass*.

    Ruled 2026-08-13 — no production change without demonstrated harm. These are
    the contracts that made "no harm" the honest answer, so they are asserted
    directly. Note what is *not* asserted: that the value is numpy. Pinning the
    defect would invert the test's purpose and make a future cleanup read as a
    regression.
    """
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 5)])
    path = str(tmp_path / "f9.dxf")
    doc.saveas(path)

    vertex = _of_kind(import_dxf(path), "polyline")[0].vertices[1]

    assert isinstance(vertex.x, float)
    assert vertex.x == 10.0
    assert math.isfinite(vertex.x)
    assert vertex.x + 1 == 11.0

    diag.ensure_json_safe({"x": vertex.x})
    assert json.loads(json.dumps({"x": vertex.x}))["x"] == 10.0


def test_f9_serialized_output_carries_no_foreign_numeric_type(tmp_path):
    """Whatever the in-memory type, the serialized document is ordinary JSON."""
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 5)])
    path = str(tmp_path / "f9b.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    blob = json.dumps(collection.to_dict())
    assert "np.float64" not in blob
    assert "numpy" not in blob

    restored = GeometryCollection.from_dict(json.loads(blob))
    original_vertex = _of_kind(collection, "polyline")[0].vertices[1]
    restored_vertex = _of_kind(restored, "polyline")[0].vertices[1]
    assert type(restored_vertex.x) is float
    assert restored_vertex.x == original_vertex.x


# --------------------------------------------------------------------------
# F10 — periodic state, answered on real DXF
# --------------------------------------------------------------------------

def test_f10_periodic_spline_is_distinguishable_from_a_merely_closed_one():
    """The question the audit could not answer, now answered from a file.

    The fixture holds two splines with identical control points differing only in
    the PERIODIC flag bit. The audit's concern was that the model collapsed DXF
    flags into a single boolean — true at ``637a0ca``, and no longer true. Both
    are closed; only one is periodic, and the import tells them apart.

    Asserted from a real DXF rather than a stub on purpose: the pre-existing
    assertion in ``test_spline_fidelity.py`` runs through a duck-typed fake, which
    proves the decode but not that the bit survives authoring and re-reading.
    """
    splines = _of_kind(_load("periodic_spline.dxf"), "spline")
    assert len(splines) == 2, "fixture must carry the closed/periodic pair"

    closed_only, closed_and_periodic = splines

    assert closed_only.closed is True
    assert closed_and_periodic.closed is True
    assert closed_only.periodic is False
    assert closed_and_periodic.periodic is True

    assert closed_only.representation == "control"
    assert [(p.x, p.y) for p in closed_only.control_points] == pytest.approx(
        [(p.x, p.y) for p in closed_and_periodic.control_points]), (
        "only the flag may differ, or the comparison proves nothing")


# --------------------------------------------------------------------------
# Cross-cutting: the findings must hold together, not merely one at a time
# --------------------------------------------------------------------------

def test_every_canonical_code_is_documented_and_the_registry_has_no_strays():
    documented = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "GEOMETRY_IMPORT.md")
    text = open(documented, encoding="utf-8").read()
    for code in diag.CANONICAL_CODES:
        assert code in text, f"{code} is registered but absent from the docs"


def test_the_whole_corpus_imports_and_round_trips_deterministically():
    """Serialization is where several findings meet; drift here is silent."""
    for name in sorted(f for f in os.listdir(FIXTURES) if f.endswith(".dxf")):
        collection = _load(name)
        blob = json.dumps(collection.to_dict())
        restored = GeometryCollection.from_dict(json.loads(blob))
        assert json.dumps(restored.to_dict()) == blob, (
            f"{name} did not round-trip identically")
