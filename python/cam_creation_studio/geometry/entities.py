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
ELLIPSE, TEXT, HATCH, DIMENSION, and INSERT/block references are unsupported
(:data:`~geometry.diagnostics.UNSUPPORTED_ENTITY`).

Splines preserve whichever representation the source used — control points or
fit points — along with knots, weights, degree, closure, and periodicity. Neither
form is converted into the other, so a fit-point spline is recorded as fit
evidence rather than reported as a loss.

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
from .models import (
    REPRESENTATION_CONTROL,
    REPRESENTATION_FIT,
    Arc2D,
    Circle2D,
    Entity,
    Line2D,
    Polyline2D,
    Spline2D,
)

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
# A point fed through a candidate mapper once, to prove it actually applies before
# we hand it to _pt. See _ocs_to_wcs.
#
# The origin is chosen deliberately: every OCS maps it to the origin, so the probe
# exercises the call path without depending on what the transform computes. It
# asserts nothing about the mapper's arithmetic — only that invoking it does not
# raise. A mapper that succeeds here and fails on a later point would defeat this,
# but an OCS transform is linear, so there is no such point.
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


def _polyline_vertices_are_wcs(entity) -> bool:
    """True for POLYLINE flavours whose vertices are already WCS, not OCS.

    Scoped to POLYLINE: it reads the POLYLINE-specific flags and means nothing for
    any other entity type. A 3D polyline is the obvious case. Polygon meshes and
    polyface meshes are the non-obvious ones: both report ``is_3d_polyline`` False
    yet also store WCS vertices, so keying only off ``is_3d_polyline`` mirrors them
    wrongly.
    """
    return any(bool(getattr(entity, flag, False)) for flag in (
        "is_3d_polyline", "is_polygon_mesh", "is_poly_face_mesh"))


def _source_elevation(entity) -> float:
    """The entity's OCS z, read per the DXF family that owns it (CS-008R F5).

    The two 2D polyline families spell the same fact differently, which is what
    made the earlier comparison against a 3D polyline misleading:

    * ``LWPOLYLINE`` stores a scalar ``dxf.elevation``.
    * 2D ``POLYLINE`` stores a *point* ``dxf.elevation`` whose z carries the
      value; its vertices sit at z = 0.

    A 3D polyline has no elevation at all — its vertices carry z directly — so
    this is never asked of one. Returns 0.0 when absent or unreadable: an entity
    that declares no elevation is at z = 0, which is a fact rather than a loss,
    so it is silent per the module's rule that correct behaviour is not reported.
    """
    raw = getattr(getattr(entity, "dxf", None), "elevation", None)
    if raw is None:
        return 0.0
    if hasattr(raw, "z"):            # 2D POLYLINE: a point, only z is meaningful
        raw = raw.z
    elif isinstance(raw, (tuple, list)):
        raw = raw[2] if len(raw) > 2 else 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _report_non_planar_chain(ext, loc: dict, diags: List[GeometryDiagnostic],
                             vertex_count: int) -> None:
    """Report a vertex chain that resolved to WCS but does not lie parallel to XY.

    The transform succeeded and every vertex is placed correctly; what is lost is
    that no planar reading of them recovers the authored profile, because the XY
    projection is foreshortened. That is a fidelity limit, not a failure, so it
    carries :data:`~geometry.diagnostics.NON_PLANAR_GEOMETRY`.

    **Silent below two vertices.** A chain that short has no profile to
    foreshorten, so the message would assert a distortion that does not exist —
    and a diagnostic stating a false reason is the exact defect this code split
    was introduced to remove. Such a chain already reports
    :data:`~geometry.diagnostics.DEGENERATE_POLYLINE`, which is the accurate
    finding; adding non-planarity on top would be noise wearing evidence's
    clothes.
    """
    if vertex_count < 2:
        return
    diags.append(diag.warning(
        diag.NON_PLANAR_GEOMETRY,
        f"Polyline plane is not parallel to WCS XY (extrusion {ext}); vertices are "
        "placed correctly in WCS but the chain is not XY-planar, so its XY "
        "projection is foreshortened relative to the authored shape.", **loc))


def _ocs_to_wcs(entity, loc: dict, diags: List[GeometryDiagnostic]):
    """ezdxf's OCS->WCS mapper for this entity, or None when no transform applies.

    Returns None in three cases, only one of which is a failure:

    * **Default extrusion** — the OCS is the world system, so there is nothing to
      apply. Quiet; this is the ordinary path.
    * **No ``ocs()`` while a non-default extrusion is declared** — reported as
      :data:`~geometry.diagnostics.OCS_TRANSFORM_FAILED`. Coordinates are left
      untransformed and may be misplaced.
    * **``ocs()`` or the mapper raised** — reported the same way.

    An object with no declared extrusion and no ``ocs()`` is not a failure: it
    simply needs no transform, which is why the default-extrusion check comes
    first and why a minimal duck-typed object works here.
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
        # Elevation is the vertices' OCS z, not a value to add afterwards. It goes
        # into the point *before* the transform because the OCS mapper mixes the
        # axes: under extrusion (0,0,-1) an OCS z of 25 resolves to a WCS z of -25,
        # and under a tilted extrusion it moves x and y as well. Transforming a
        # flat (x, y, 0) and adding elevation after would be wrong in both cases.
        elevation = _source_elevation(entity)
        if to_wcs is None:
            verts = [Point(p[0] * scale, p[1] * scale, elevation * scale)
                     for p in pts]
        else:
            verts = [_pt((p[0], p[1], elevation), scale, to_wcs) for p in pts]
            ext = _extrusion_of(entity)
            if not _xy_planar(ext):
                _report_non_planar_chain(ext, loc, diags, len(verts))
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
        wcs_vertices = _polyline_vertices_are_wcs(entity)
        to_wcs = None if wcs_vertices else _ocs_to_wcs(entity, loc, diags)
        if wcs_vertices:
            # 3D polylines and the mesh flavours carry z on each vertex already;
            # they have no elevation attribute and must not be given one.
            verts = [_pt(v.dxf.location, scale, to_wcs) for v in entity.vertices]
        else:
            # A 2D POLYLINE's vertices sit at z = 0 and the entity's elevation
            # point carries the real OCS z. Fold it in before the transform, for
            # the same reason as LWPOLYLINE above. Vertex locations are read
            # through _as_xyz because they may be attribute-style or index-style
            # vectors, exactly as _pt allows.
            elevation = _source_elevation(entity)
            verts = []
            for v in entity.vertices:
                x, y, _z = _as_xyz(v.dxf.location) or (0.0, 0.0, 0.0)
                verts.append(_pt((x, y, elevation), scale, to_wcs))
        ext = _extrusion_of(entity)
        if to_wcs is not None and not _xy_planar(ext):
            _report_non_planar_chain(ext, loc, diags, len(verts))
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
        return _translate_spline(entity, scale, layer, loc)

    # Unsupported: keep evidence, drop no geometry silently.
    return None, [diag.warning(
        diag.UNSUPPORTED_ENTITY, f"Unsupported DXF entity type {dxftype!r}.", **loc)]


# --------------------------------------------------------------------------- #
# SPLINE
# --------------------------------------------------------------------------- #
# DXF SPLINE flag bits (group code 70).
_SPLINE_CLOSED = 1
_SPLINE_PERIODIC = 2
_SPLINE_RATIONAL = 4


def _floats(values) -> Optional[List[float]]:
    """A plain float list from any sequence-like, unscaled, or None if unreadable.

    Returns ``None`` rather than raising when the source holds something
    non-numeric. A malformed knot or weight array is bad data in the file, and
    this module's contract is to report bad data as evidence — letting a
    ``ValueError`` escape would abort the whole import over one entity, losing
    every other entity in the file along with it.

    Knots live in parameter space and weights are dimensionless: neither is a
    length, so neither is multiplied by the unit scale.
    """
    try:
        return [float(v) for v in (values or [])]
    except (TypeError, ValueError):
        return None


def _translate_spline(entity, scale: float, layer: str, loc: dict) -> TranslationResult:
    """Preserve a SPLINE as the source defined it — control points or fit points.

    A spline given by fit points is *not* an incomplete control-point spline; it
    is a different, equally complete description. Recording it as such preserves
    the source faithfully, so no loss diagnostic is raised. Converting between the
    two is curve fitting, which this layer does not do.

    Diagnostics are reserved for genuine loss:

    * neither representation available -> the entity is not geometry, so it is
      excluded rather than admitted as an empty-but-valid spline;
    * weights that cannot be matched to control points 1:1 -> the association is
      unrecoverable, so the weights are dropped and said so;
    * a fit spline carrying tangent constraints -> the tangents shape the curve
      and this model has nowhere to put them.
    """
    ctrl = [_pt(p, scale) for p in (getattr(entity, "control_points", None) or [])]
    fit = [_pt(p, scale) for p in (getattr(entity, "fit_points", None) or [])]
    degree = int(getattr(entity.dxf, "degree", 3))
    flags = int(getattr(entity.dxf, "flags", 0) or 0)
    knots = _floats(getattr(entity, "knots", None))
    weights = _floats(getattr(entity, "weights", None))
    diags: List[GeometryDiagnostic] = []

    # A non-numeric knot or weight array is malformed source data. Report it and
    # carry on without that array rather than letting the conversion raise, which
    # would abandon every other entity in the file over this one.
    for name, values in (("knot", knots), ("weight", weights)):
        if values is None:
            diags.append(diag.warning(
                diag.INVALID_SPLINE,
                f"Spline {name} values are not numeric; the {name} array was "
                "discarded and the rest of the spline imported.", **loc))
    knots = knots if knots is not None else []
    weights = weights if weights is not None else []

    # Degree below 1 is not a curve. ezdxf refuses to author it, so this only
    # arrives from a malformed file; the value is preserved as evidence but must
    # not pass as ordinary.
    if degree < 1:
        diags.append(diag.warning(
            diag.INVALID_SPLINE,
            f"Spline declares degree {degree}; a spline degree below 1 does not "
            "describe a curve.", **loc))

    if not ctrl and not fit:
        return None, [diag.loss(
            diag.EMPTY_SPLINE_GEOMETRY,
            "Spline carries neither control points nor fit points; it defines no "
            "geometry and was not imported.",
            recoverable=False,
            metadata={"degree": degree, "knot_count": len(knots)},
            **loc)]

    # Control points win when both are present: they define the curve exactly,
    # while fit points are the authoring intent the CAD tool fitted them to.
    representation = REPRESENTATION_CONTROL if ctrl else REPRESENTATION_FIT

    # Weights are positional — weight[i] belongs to control_points[i]. Without a
    # 1:1 match that mapping is unrecoverable, so the weights cannot be preserved.
    # The two ways this happens read very differently to whoever gets the
    # diagnostic, so they are worded differently: a fit-represented spline has no
    # control points at all, which is not a "count mismatch" but weights arriving
    # on a representation that has nothing to attach them to.
    if weights and len(weights) != len(ctrl):
        if representation == REPRESENTATION_FIT:
            reason = (f"Spline is defined by fit points and carries no control "
                      f"points, so its {len(weights)} weight(s) have nothing to "
                      "attach to and were dropped.")
        else:
            reason = (f"Spline has {len(weights)} weight(s) for {len(ctrl)} "
                      "control point(s); the association is unrecoverable, so "
                      "weights were dropped.")
        diags.append(diag.loss(
            diag.RATIONAL_SPLINE_WEIGHTS_DROPPED, reason,
            recoverable=False,
            metadata={"weight_count": len(weights),
                      "control_point_count": len(ctrl),
                      "representation": representation,
                      "degree": degree},
            **loc))
        weights = []

    # Tangent constraints shape a fitted curve. We keep the fit points, but this
    # model has nowhere to record the tangents, so the curve is under-determined.
    tangents = [
        name for name in ("start_tangent", "end_tangent")
        if _dxf_has(entity, name)
    ]
    if representation == REPRESENTATION_FIT and tangents:
        diags.append(diag.loss(
            diag.FIT_POINT_SPLINE_UNREPRESENTED,
            f"Fit-point spline carries {' and '.join(tangents)}; the fit points "
            "are preserved but the tangent constraints are not represented.",
            recoverable=False,
            metadata={"fit_point_count": len(fit), "tangents": tangents,
                      "degree": degree},
            **loc))

    # An under-specified control-point spline is still advisory, not a loss: the
    # points we were given are all preserved. Only meaningful for the control
    # representation — a fit spline is not expected to carry control points.
    if representation == REPRESENTATION_CONTROL and len(ctrl) < degree + 1:
        diags.append(diag.warning(
            diag.INVALID_SPLINE,
            f"Spline of degree {degree} has only {len(ctrl)} control points.",
            **loc))

    return (
        Spline2D(
            control_points=ctrl,
            fit_points=fit,
            knots=knots,
            weights=weights,
            degree=degree,
            closed=bool(getattr(entity, "closed", False) or flags & _SPLINE_CLOSED),
            periodic=bool(flags & _SPLINE_PERIODIC),
            rational=bool(flags & _SPLINE_RATIONAL) or bool(weights),
            representation=representation,
            layer=layer,
        ),
        diags,
    )


def _dxf_has(entity, name: str) -> bool:
    """True when the entity's DXF namespace actually carries ``name``.

    ezdxf exposes ``dxf.hasattr``; a duck-typed stand-in may not, so fall back to
    a plain attribute probe rather than requiring the richer interface.
    """
    dxf = getattr(entity, "dxf", None)
    if dxf is None:
        return False
    has = getattr(dxf, "hasattr", None)
    if callable(has):
        return bool(has(name))
    return getattr(dxf, name, None) is not None
