"""One-time generator for the CS-008 golden DXF corpus. NOT run by the tests.

The ``.dxf`` files beside this script are an **immutable** fixture corpus: they
are committed, reviewed as text (ASCII DXF), and never regenerated as part of a
test run. This script exists so the corpus is reproducible and its provenance is
auditable — not so CI can rebuild it.

Regenerating would silently re-baseline every characterization test against a
new file, which is precisely the class of invisible change CS-008 remediation
exists to prevent. If a fixture genuinely needs to change, add a new one with a
new name and leave the old file alone.

To regenerate deliberately (e.g. a new fixture):

    python python/tests/fixtures/MAKE_FIXTURES.py

Requires the optional ``ezdxf`` extra. Written with ezdxf 1.4.3.

Each fixture isolates exactly one fidelity question, so a failing test names the
defect by naming the file.
"""

from __future__ import annotations

import os

import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))


def _new():
    """A millimetre document; R2010 is new enough for LWPOLYLINE and splines."""
    doc = ezdxf.new("R2010")
    doc.units = 4  # INSUNITS 4 == millimetres
    return doc, doc.modelspace()


def lwpolyline_elevated():
    """LWPOLYLINE carrying elevation 25 — the Z the importer currently drops."""
    doc, msp = _new()
    pl = msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
    pl.dxf.elevation = 25.0
    return doc, "lwpolyline_elevated.dxf"


def lwpolyline_elevation():
    """CS-008R F5 control, half one: LWPOLYLINE with a scalar ``dxf.elevation``.

    Paired with :func:`polyline2d_elevation`, which authors the *same* square at
    the *same* height through the other 2D representation. Together they are the
    correct version of the comparison the withdrawn ``polyline_elevated`` fixture
    got wrong: equivalent authored geometry, genuinely equivalent DXF semantics.
    """
    doc, msp = _new()
    pl = msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
    pl.dxf.elevation = 25.0
    return doc, "lwpolyline_elevation.dxf"


def polyline2d_elevation():
    """CS-008R F5 control, half two: a true **2D** POLYLINE at the same height.

    ``add_polyline2d`` — never ``add_polyline3d``. The distinction is the entire
    point of this fixture:

    * a 2D POLYLINE keeps its vertices at z = 0 and carries the height in
      ``dxf.elevation``, which is a *point* whose z holds the value;
    * a 3D POLYLINE has no elevation attribute at all and carries z on each
      vertex.

    Comparing a 2D LWPOLYLINE against a 3D POLYLINE therefore compares two
    different things and manufactures an asymmetry that does not exist. That is
    exactly what happened, and audit probe P8c disproved it. This pair replaces
    that comparison; see the note below where the bad builder used to be.
    """
    doc, msp = _new()
    msp.add_polyline2d([(0, 0), (10, 0), (10, 10), (0, 10)], close=True,
                       dxfattribs={"elevation": (0, 0, 25.0)})
    return doc, "polyline2d_elevation.dxf"


# A ``polyline_elevated`` builder was removed here, deliberately.
#
# It claimed to be an elevation control paired with ``lwpolyline_elevated`` —
# "identical geometry, different DXF entity, so any divergence is attributable to
# the import path" — while building the fixture with ``add_polyline3d``. That is
# not identical geometry: a 3D polyline carries Z in its vertices, whereas a 2D
# POLYLINE carries it in the ``elevation`` attribute. Any divergence it showed was
# caused by the fixture, not by the importer.
#
# It produced a withdrawn claim that the LWPOLYLINE and POLYLINE paths behave
# differently. The CS-008R audit's probe P8c disproves that: a *2D* POLYLINE drops
# elevation exactly as LWPOLYLINE does. See docs/audits/CS-008_REAUDIT.md F5.
#
# A correct control needs a 2D polyline with ``dxf.elevation`` set. Adding it
# belongs to the F5 remediation, which owns that finding — not to this evidence
# increment. It is left unwritten rather than written wrong, because this corpus
# is immutable and a misleading fixture cannot be quietly corrected later.
#
# **Written now, correctly**, by the F5 remediation that owns it: the pair
# `lwpolyline_elevation` / `polyline2d_elevation` above. The withdrawn file keeps
# its old name and is never reused as an elevation control.


def extruded_circle():
    """CIRCLE at OCS (5,5) with extrusion (0,0,-1) — true WCS centre is (-5,5).

    A flipped extrusion mirrors the OCS X axis. Importing the raw OCS centre
    places the circle at +5 instead of -5: not lost metadata, a wrong position.
    """
    doc, msp = _new()
    c = msp.add_circle((5, 5), 3)
    c.dxf.extrusion = (0, 0, -1)
    return doc, "extruded_circle.dxf"


def ocs_arc():
    """ARC on a tilted plane — extrusion is neither +Z nor a simple flip.

    Exercises the general OCS case (arbitrary-axis algorithm) rather than the
    degenerate mirror that ``extruded_circle`` covers.
    """
    doc, msp = _new()
    a = msp.add_arc((10, 0), radius=5, start_angle=0, end_angle=90)
    a.dxf.extrusion = (0.0, 0.6, 0.8)  # unit vector, tilted about X
    return doc, "ocs_arc.dxf"


def fit_spline():
    """SPLINE defined by fit points only — currently imports with zero control points."""
    doc, msp = _new()
    msp.add_spline(fit_points=[(0, 0), (5, 5), (10, 0), (15, 5)])
    return doc, "fit_spline.dxf"


def weighted_spline():
    """Rational SPLINE with non-uniform weights — currently discarded silently."""
    doc, msp = _new()
    msp.add_rational_spline(
        control_points=[(0, 0), (1, 2), (2, 0), (3, 2)],
        weights=[1.0, 4.0, 4.0, 1.0],
        degree=3,
    )
    return doc, "weighted_spline.dxf"


def unsupported_entity():
    """An ELLIPSE plus one LINE — the unsupported path, with survivors alongside.

    The LINE matters: it proves an unsupported entity is dropped without taking
    the rest of the drawing with it.
    """
    doc, msp = _new()
    msp.add_line((0, 0), (10, 0))
    msp.add_ellipse((5, 5), major_axis=(4, 0), ratio=0.5)
    return doc, "unsupported_entity.dxf"


BUILDERS = (
    lwpolyline_elevated,
    lwpolyline_elevation,
    polyline2d_elevation,
    extruded_circle,
    ocs_arc,
    fit_spline,
    weighted_spline,
    unsupported_entity,
)


def main() -> None:
    for build in BUILDERS:
        doc, name = build()
        path = os.path.join(HERE, name)
        doc.saveas(path)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
