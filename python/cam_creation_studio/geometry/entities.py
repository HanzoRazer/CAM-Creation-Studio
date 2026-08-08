"""Translate ezdxf entities into neutral geometry models (CS-008).

This is the *only* module that reads ezdxf entity objects, and it never leaks
one outside: every function returns internal :mod:`geometry.models` dataclasses.
It imports no ezdxf symbols at module load — it merely duck-types the attributes
ezdxf entities expose — so it stays importable in a dep-free environment.

Coordinates are normalized to millimetres here by applying the importer-supplied
``scale``, and to WORLD coordinates by resolving each entity's Object Coordinate
System (see the OCS section below). Per-entity issues (zero-length line, zero
radius, degenerate polyline, invalid spline, flattened bulge, unresolvable OCS)
become advisory diagnostics; the geometry is still kept, so no entity is ever lost
silently.

Fidelity limits (surfaced as diagnostics, never silent): polyline *bulges* are
flattened to chords (:data:`~geometry.diagnostics.POLYLINE_BULGE_IGNORED`);
splines keep only control points + degree (knot vectors, weights, and fit points
are dropped); ELLIPSE, TEXT, HATCH, DIMENSION, and INSERT/block references are
unsupported (:data:`~geometry.diagnostics.UNSUPPORTED_ENTITY`).

Two distinct OCS outcomes are reported, and the difference is load-bearing for any
consumer making policy decisions from diagnostics:

``OCS_TRANSFORM_FAILED``
    The transform could not be obtained or applied, so coordinates were left
    untransformed and may be misplaced.
``NON_PLANAR_GEOMETRY``
    The transform succeeded and every coordinate is correct, but the result is not
    parallel to WCS XY, so this 2D model cannot represent it faithfully — a tilted
    circle is really an ellipse in XY, and a tilted vertex chain's XY projection is
    foreshortened. A consumer needing a planar profile must check for this; the
    model types themselves promise no planarity.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..shared.geometry import Point
from . import diagnostics as diag
from .diagnostics import GeometryDiagnostic
from .models import Arc2D, Circle2D, Entity, Line2D, Polyline2D, Spline2D

TranslationResult = Tuple[Optional[Entity], List[GeometryDiagnostic]]

# DXF entity types we can represent as neutral geometry.
SUPPORTED_TYPES = frozenset(
    {"LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE"}
)

# Degeneracy tolerance (millimetres, applied post-scale). Small enough that no
# real feature trips it, large enough to catch float noise from CAD exports that
# an exact ``== 0`` comparison would miss.
_DEGENERATE_EPS_MM = 1e-9


def _has_bulge(bulges) -> bool:
    """True if any bulge value is non-negligible (an arc, not a straight chord)."""
    return any(abs(float(b)) > _DEGENERATE_EPS_MM for b in bulges)


def _pt(vec, scale: float, to_wcs=None) -> Point:
    """A shared Point from any ezdxf vector-like, in WCS millimetres.

    Accepts both attribute-style vectors (``.x/.y/.z``, e.g. ezdxf ``Vec3``) and
    index-style sequences (``vec[0]/[1]/[2]``, e.g. numpy arrays returned for
    spline control points).

    ``to_wcs`` is ezdxf's OCS mapper for the owning entity, supplied only for
    OCS-defined coordinates on a non-default extrusion. Without it the coordinates
    are passed through exactly as before, so default-extrusion output is unchanged.
    The transform is applied before scaling; since the scale is uniform the order
    is numerically immaterial, but transforming first keeps the mapper operating on
    true source units.
    """
    if hasattr(vec, "x"):
        x, y = vec.x, vec.y
        z = getattr(vec, "z", 0.0)
    else:
        x, y = vec[0], vec[1]
        z = vec[2] if len(vec) > 2 else 0.0
    x, y, z = float(x), float(y), float(z or 0.0)
    if to_wcs is not None:
        w = to_wcs((x, y, z))
        x, y, z = float(w.x), float(w.y), float(w.z)
    return Point(x * scale, y * scale, z * scale)


def _layer_of(entity) -> str:
    layer = getattr(getattr(entity, "dxf", None), "layer", None)
    return layer if layer else "0"


def _handle_of(entity) -> Optional[str]:
    return getattr(getattr(entity, "dxf", None), "handle", None)


# --------------------------------------------------------------------------- #
# Object Coordinate System (CS-008R F1)
#
# DXF stores CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE coordinates in the entity's
# Object Coordinate System, not in world coordinates. When an entity carries a
# non-default extrusion — the ordinary result of mirroring or rotating in CAD —
# reading those numbers as if they were WCS places the geometry somewhere else
# entirely. LINE endpoints and SPLINE control points are already WCS and are left
# alone.
#
# ezdxf's own OCS implementation is the authority here (``entity.ocs()``), reached
# by duck typing so this module still imports with no ezdxf present. We do NOT
# reimplement the arbitrary-axis algorithm.
# --------------------------------------------------------------------------- #
_DEFAULT_EXTRUSION = (0.0, 0.0, 1.0)
# How far the extrusion may tilt off the Z axis before the entity's plane is no
# longer parallel to WCS XY. Below this the plane is XY-parallel for our purposes.
_PLANAR_EPS = 1e-9
# An arbitrary point fed through a candidate mapper once, to prove it actually
# applies before we hand it to _pt. See _ocs_to_wcs.
_MAPPER_PROBE_POINT = (0.0, 0.0, 0.0)


def _as_xyz(vec) -> Optional[tuple]:
    """(x, y, z) floats from an attribute-style or index-style vector, else None."""
    if vec is None:
        return None
    try:
        if hasattr(vec, "x"):
            return (float(vec.x), float(vec.y), float(getattr(vec, "z", 0.0) or 0.0))
        return (float(vec[0]), float(vec[1]), float(vec[2]) if len(vec) > 2 else 0.0)
    except (TypeError, ValueError, IndexError):
        return None


def _extrusion_of(entity) -> Optional[tuple]:
    return _as_xyz(getattr(getattr(entity, "dxf", None), "extrusion", None))


def _is_default_extrusion(ext: Optional[tuple]) -> bool:
    """True when the entity's OCS is the world system (or declares no extrusion).

    Entities on the default extrusion take the untouched pass-through path, so
    their imported coordinates are bit-identical to what they were before F1.
    """
    if ext is None:
        return True
    return all(abs(a - b) <= _PLANAR_EPS for a, b in zip(ext, _DEFAULT_EXTRUSION))


def _xy_planar(ext: Optional[tuple]) -> bool:
    """True when the OCS xy-plane is parallel to the WCS XY plane.

    Only then can a swept ARC (or a CIRCLE) be represented faithfully by our 2D
    model, whose angles and radius live in the XY plane — and only then does a
    vertex chain keep its authored proportions when read as a planar profile.
    """
    if ext is None:
        return True
    x, y, z = ext
    return abs(x) <= _PLANAR_EPS and abs(y) <= _PLANAR_EPS and abs(abs(z) - 1.0) <= _PLANAR_EPS


def _wcs_vertex_polyline(entity) -> bool:
    """True for POLYLINE flavours whose vertices are already WCS, not OCS.

    A 3D polyline is the obvious one. Polygon meshes and polyface meshes are the
    non-obvious ones: both report ``is_3d_polyline`` False yet also store WCS
    vertices, so keying only off ``is_3d_polyline`` mirrors them wrongly.
    """
    return any(bool(getattr(entity, flag, False)) for flag in (
        "is_3d_polyline", "is_polygon_mesh", "is_poly_face_mesh"))


def _report_non_planar_chain(ext, loc: dict, diags: List[GeometryDiagnostic]) -> None:
    """Report a vertex chain that resolved to WCS but does not lie parallel to XY.

    The transform succeeded and every vertex is placed correctly; what is lost is
    that no planar reading of them recovers the authored profile, because the XY
    projection is foreshortened. That is a fidelity limit, not a failure, so it
    carries :data:`~geometry.diagnostics.NON_PLANAR_GEOMETRY`.
    """
    diags.append(diag.warning(
        diag.NON_PLANAR_GEOMETRY,
        f"Polyline plane is not parallel to WCS XY (extrusion {ext}); vertices are "
        "placed correctly in WCS but the chain is not XY-planar, so its XY "
        "projection is foreshortened relative to the authored shape.", **loc))


def _ocs_to_wcs(entity, loc: dict, diags: List[GeometryDiagnostic]):
    """ezdxf's OCS->WCS mapper for this entity, or None when none is needed.

    Returns None for a default extrusion (identity, pass-through) and for objects
    that expose no ``ocs()`` at all — a duck-typed test double is not a failure.
    A declared non-default extrusion that we cannot resolve IS a failure and is
    reported, because it means geometry may be placed incorrectly.
    """
    ext = _extrusion_of(entity)
    if _is_default_extrusion(ext):
        return None

    ocs_factory = getattr(entity, "ocs", None)
    if ocs_factory is None:
        diags.append(diag.warning(
            diag.OCS_TRANSFORM_FAILED,
            f"Entity declares extrusion {ext} but exposes no OCS; coordinates are "
            "left untransformed and may be misplaced.", **loc))
        return None

    # Any failure to obtain the authoritative transform must surface as evidence
    # rather than abort the import or silently fall through to raw coordinates.
    # The mapper is probed once here rather than merely fetched: obtaining it can
    # succeed while *applying* it raises, and an exception raised later from inside
    # _pt would escape this guard and abort the whole import.
    try:
        to_wcs = ocs_factory().to_wcs
        to_wcs(_MAPPER_PROBE_POINT)
        return to_wcs
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        diags.append(diag.warning(
            diag.OCS_TRANSFORM_FAILED,
            f"Could not resolve OCS for extrusion {ext}: {exc}", **loc))
        return None


def translate(entity, scale: float) -> TranslationResult:
    """Convert one ezdxf ``entity`` to an internal model + any diagnostics.

    Returns ``(None, [diag])`` for unsupported types; ``(entity, diags)``
    otherwise (``diags`` may be empty).
    """
    dxftype = entity.dxftype()
    layer = _layer_of(entity)
    handle = _handle_of(entity)
    loc = {"entity_type": dxftype, "handle": handle, "layer": layer}

    if dxftype == "LINE":
        start = _pt(entity.dxf.start, scale)
        end = _pt(entity.dxf.end, scale)
        diags: List[GeometryDiagnostic] = []
        if start.distance_to(end) <= _DEGENERATE_EPS_MM:
            diags.append(diag.warning(
                diag.ZERO_LENGTH_LINE, "Line has zero length.", **loc))
        return Line2D(start=start, end=end, layer=layer), diags

    if dxftype == "ARC":
        diags = []
        to_wcs = _ocs_to_wcs(entity, loc, diags)
        ext = _extrusion_of(entity)
        center = _pt(entity.dxf.center, scale, to_wcs)
        radius = float(entity.dxf.radius) * scale
        start_angle = float(entity.dxf.start_angle)
        end_angle = float(entity.dxf.end_angle)
        if to_wcs is not None:
            if _xy_planar(ext):
                # The OCS xy-plane is parallel to WCS XY, so the sweep maps exactly.
                # A negative extrusion reflects the plane: a CCW sweep in OCS reads
                # as CW in WCS, so mirror each angle about 180 deg and swap the
                # endpoints to keep Arc2D's documented CCW start->end convention.
                if ext[2] < 0:
                    start_angle, end_angle = 180.0 - end_angle, 180.0 - start_angle
            else:
                # A tilted extrusion puts the arc in a plane our 2D model cannot
                # express. The transform succeeded and the centre is placed
                # correctly; the sweep is not an XY sweep, and that fidelity limit
                # is reported rather than left quietly wrong.
                diags.append(diag.warning(
                    diag.NON_PLANAR_GEOMETRY,
                    f"Arc plane is not parallel to WCS XY (extrusion {ext}); centre "
                    "is placed in WCS but sweep angles could not be normalized.",
                    **loc))
        if abs(radius) <= _DEGENERATE_EPS_MM:
            diags.append(diag.warning(
                diag.ZERO_RADIUS, "Arc has zero radius.", **loc))
        return (
            Arc2D(
                center=center,
                radius=radius,
                start_angle=start_angle,
                end_angle=end_angle,
                layer=layer,
            ),
            diags,
        )

    if dxftype == "CIRCLE":
        diags = []
        to_wcs = _ocs_to_wcs(entity, loc, diags)
        ext = _extrusion_of(entity)
        center = _pt(entity.dxf.center, scale, to_wcs)
        radius = float(entity.dxf.radius) * scale
        if to_wcs is not None and not _xy_planar(ext):
            # Transform succeeded and the centre is correct; the circle's plane is
            # tilted, so its XY footprint is really an ellipse and Circle2D
            # overstates it — a fidelity limit, not a failure.
            diags.append(diag.warning(
                diag.NON_PLANAR_GEOMETRY,
                f"Circle plane is not parallel to WCS XY (extrusion {ext}); centre "
                "is placed in WCS but the circle is not XY-planar.", **loc))
        if abs(radius) <= _DEGENERATE_EPS_MM:
            diags.append(diag.warning(
                diag.ZERO_RADIUS, "Circle has zero radius.", **loc))
        return Circle2D(center=center, radius=radius, layer=layer), diags

    if dxftype == "LWPOLYLINE":
        # "xyb" yields (x, y, bulge); a non-zero bulge is an arc we flatten to a
        # chord, so record it rather than change the shape silently.
        diags = []
        to_wcs = _ocs_to_wcs(entity, loc, diags)
        pts = list(entity.get_points("xyb"))
        if to_wcs is None:
            verts = [Point(p[0] * scale, p[1] * scale) for p in pts]
        else:
            # Vertices are OCS. Elevation is deliberately NOT folded in here: that
            # is CS-008R F5 and still out of scope, so the OCS z stays 0.
            verts = [_pt((p[0], p[1], 0.0), scale, to_wcs) for p in pts]
            if not _xy_planar(_extrusion_of(entity)):
                _report_non_planar_chain(_extrusion_of(entity), loc, diags)
        bulges = [p[2] for p in pts if len(p) > 2]
        if len(verts) < 2:
            diags.append(diag.warning(
                diag.DEGENERATE_POLYLINE,
                f"Polyline has {len(verts)} vertex/vertices.", **loc))
        if _has_bulge(bulges):
            diags.append(diag.warning(
                diag.POLYLINE_BULGE_IGNORED,
                "Polyline has bulge (arc) segments; flattened to straight chords.",
                **loc))
        return Polyline2D(vertices=verts, closed=bool(entity.closed), layer=layer), diags

    if dxftype == "POLYLINE":
        diags = []
        # Only a 2D POLYLINE is OCS-defined; 3D polylines and the mesh flavours
        # already store WCS vertices, so they must not be transformed.
        to_wcs = None if _wcs_vertex_polyline(entity) else _ocs_to_wcs(entity, loc, diags)
        verts = [_pt(v.dxf.location, scale, to_wcs) for v in entity.vertices]
        if to_wcs is not None and not _xy_planar(_extrusion_of(entity)):
            _report_non_planar_chain(_extrusion_of(entity), loc, diags)
        bulges = [getattr(v.dxf, "bulge", 0.0) for v in entity.vertices]
        if len(verts) < 2:
            diags.append(diag.warning(
                diag.DEGENERATE_POLYLINE,
                f"Polyline has {len(verts)} vertex/vertices.", **loc))
        if _has_bulge(bulges):
            diags.append(diag.warning(
                diag.POLYLINE_BULGE_IGNORED,
                "Polyline has bulge (arc) segments; flattened to straight chords.",
                **loc))
        return (
            Polyline2D(vertices=verts, closed=bool(entity.is_closed), layer=layer),
            diags,
        )

    if dxftype == "SPLINE":
        ctrl = [_pt(p, scale) for p in entity.control_points]
        degree = int(getattr(entity.dxf, "degree", 3))
        diags = []
        if len(ctrl) < degree + 1:
            diags.append(diag.warning(
                diag.INVALID_SPLINE,
                f"Spline of degree {degree} has only {len(ctrl)} control points.",
                **loc))
        return (
            Spline2D(control_points=ctrl, degree=degree,
                     closed=bool(entity.closed), layer=layer),
            diags,
        )

    # Unsupported: keep evidence, drop no geometry silently.
    return None, [diag.warning(
        diag.UNSUPPORTED_ENTITY, f"Unsupported DXF entity type {dxftype!r}.", **loc)]
