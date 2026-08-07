"""Translate ezdxf entities into neutral geometry models (CS-008).

This is the *only* module that reads ezdxf entity objects, and it never leaks
one outside: every function returns internal :mod:`geometry.models` dataclasses.
It imports no ezdxf symbols at module load — it merely duck-types the attributes
ezdxf entities expose — so it stays importable in a dep-free environment.

Coordinates are normalized to millimetres here by applying the importer-supplied
``scale``. Per-entity issues (zero-length line, zero radius, degenerate polyline,
invalid spline, flattened bulge) become advisory diagnostics; the geometry is
still kept, so no entity is ever lost silently.

Fidelity limits (surfaced as diagnostics, never silent): polyline *bulges* are
flattened to chords (:data:`~geometry.diagnostics.POLYLINE_BULGE_IGNORED`);
ELLIPSE, TEXT, HATCH, DIMENSION, and INSERT/block references are unsupported
(:data:`~geometry.diagnostics.UNSUPPORTED_ENTITY`).

Splines preserve whichever representation the source used — control points or
fit points — along with knots, weights, degree, closure, and periodicity. Neither
form is converted into the other, so a fit-point spline is recorded as fit
evidence rather than reported as a loss.
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


def _pt(vec, scale: float) -> Point:
    """A shared Point from any ezdxf vector-like, scaled to mm.

    Accepts both attribute-style vectors (``.x/.y/.z``, e.g. ezdxf ``Vec3``) and
    index-style sequences (``vec[0]/[1]/[2]``, e.g. numpy arrays returned for
    spline control points).
    """
    if hasattr(vec, "x"):
        x, y = vec.x, vec.y
        z = getattr(vec, "z", 0.0)
    else:
        x, y = vec[0], vec[1]
        z = vec[2] if len(vec) > 2 else 0.0
    return Point(float(x) * scale, float(y) * scale, float(z or 0.0) * scale)


# --------------------------------------------------------------------------- #
# Object Coordinate System (OCS)
# --------------------------------------------------------------------------- #
# DXF stores CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE coordinates in the entity's
# own OCS, defined by its extrusion vector. With the default extrusion (0,0,1)
# the OCS *is* the WCS; with any other, raw coordinates are in the wrong place —
# a (0,0,-1) extrusion mirrors X, so an untransformed import lands a part
# mirrored with nothing to show for it.
#
# The transform itself comes from ezdxf via ``entity.ocs()``. ezdxf defines DXF
# coordinate semantics and is already the importer's dependency; reimplementing
# the arbitrary-axis algorithm here would create a second correctness authority
# for the same maths. Access stays duck-typed, so this module still imports no
# ezdxf symbol and a lightweight fake without ``ocs()`` simply gets identity.

_OCS_EPS = 1e-9

# Entity types whose coordinates DXF defines in OCS. LINE and SPLINE are always
# WCS; a 3D POLYLINE is WCS while a 2D one is OCS, so it is decided per entity.
_OCS_TYPES = frozenset({"CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE"})

DEFAULT_EXTRUSION = (0.0, 0.0, 1.0)


def _vec3(value) -> Optional[Tuple[float, float, float]]:
    """A plain ``(x, y, z)`` tuple from any vector-like, or ``None``."""
    if value is None:
        return None
    if hasattr(value, "x"):
        return float(value.x), float(value.y), float(getattr(value, "z", 0.0))
    try:
        return float(value[0]), float(value[1]), float(value[2])
    except (TypeError, IndexError, ValueError):
        return None


def _extrusion_of(entity) -> Tuple[float, float, float]:
    """The entity's extrusion vector, defaulting to +Z when absent."""
    return _vec3(getattr(getattr(entity, "dxf", None), "extrusion", None)) or DEFAULT_EXTRUSION


def _is_default_extrusion(extrusion) -> bool:
    """True when the OCS coincides with the WCS and no transform is needed."""
    x, y, z = extrusion
    return abs(x) <= _OCS_EPS and abs(y) <= _OCS_EPS and abs(z - 1.0) <= _OCS_EPS


def _is_planar_extrusion(extrusion) -> bool:
    """True when the entity's plane is parallel to WCS XY (extrusion ±Z).

    Only these can be represented by the planar :class:`Arc2D` / :class:`Circle2D`
    models: any other extrusion tilts the circle out of the XY plane entirely.
    """
    x, y, z = extrusion
    return abs(x) <= _OCS_EPS and abs(y) <= _OCS_EPS and abs(abs(z) - 1.0) <= _OCS_EPS


def _uses_ocs(entity, dxftype: str) -> bool:
    """True when this entity's coordinates need an OCS→WCS transform."""
    if dxftype not in _OCS_TYPES:
        return False
    if dxftype == "POLYLINE" and not getattr(entity, "is_2d_polyline", False):
        return False  # a 3D polyline's vertices are already WCS
    return not _is_default_extrusion(_extrusion_of(entity))


def _wcs_mapper(entity):
    """A callable mapping OCS ``(x, y, z)`` to WCS, or ``None`` if unavailable.

    Uses ezdxf's own ``entity.ocs()``; a duck-typed stand-in without it yields
    ``None`` and the caller falls back to identity.
    """
    ocs_factory = getattr(entity, "ocs", None)
    if not callable(ocs_factory):
        return None
    ocs = ocs_factory()
    to_wcs = getattr(ocs, "to_wcs", None)
    if not callable(to_wcs):
        return None

    def _map(x: float, y: float, z: float):
        return _vec3(to_wcs((x, y, z)))

    return _map


def _mirror_arc_angles(start: float, end: float) -> Tuple[float, float]:
    """Angles for an arc whose plane is mirrored by a (0,0,-1) extrusion.

    A mirror reverses orientation, and :class:`Arc2D` is defined as sweeping
    **counter-clockwise** from ``start_angle`` to ``end_angle``. Both the locus
    and the start/end identity cannot survive that — so we keep the locus, which
    is the geometry, and accept that the two endpoints trade roles.

    Reflection about the Y axis sends θ to 180° − θ; reversing the sweep swaps
    the two, giving ``(180 − end, 180 − start)``. Verified against ezdxf's own
    ``start_point`` / ``end_point`` for a mirrored arc.
    """
    return (180.0 - end) % 360.0, (180.0 - start) % 360.0


def _layer_of(entity) -> str:
    layer = getattr(getattr(entity, "dxf", None), "layer", None)
    return layer if layer else "0"


def _handle_of(entity) -> Optional[str]:
    return getattr(getattr(entity, "dxf", None), "handle", None)


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

    if dxftype in ("ARC", "CIRCLE"):
        return _translate_circular(entity, dxftype, scale, layer, loc)

    if dxftype == "LWPOLYLINE":
        # "xyb" yields (x, y, bulge); a non-zero bulge is an arc we flatten to a
        # chord, so record it rather than change the shape silently. Vertices are
        # OCS 2D at the entity's `elevation`, which is the Z the old path lost.
        pts = list(entity.get_points("xyb"))
        elevation = float(getattr(entity.dxf, "elevation", 0.0) or 0.0)
        to_wcs = _wcs_mapper(entity) if _uses_ocs(entity, dxftype) else None
        extrusion = _extrusion_of(entity)

        verts = []
        for p in pts:
            x, y = float(p[0]), float(p[1])
            if to_wcs is not None:
                mapped = to_wcs(x, y, elevation)
                if mapped is not None:
                    x, y, z = mapped
                else:
                    z = elevation
            else:
                z = elevation
            verts.append(Point(x * scale, y * scale, z * scale))

        bulges = [p[2] for p in pts if len(p) > 2]
        diags = []
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
            Polyline2D(
                vertices=verts, closed=bool(entity.closed), layer=layer,
                extrusion=None if _is_default_extrusion(extrusion) else Point(*extrusion),
            ),
            diags,
        )

    if dxftype == "POLYLINE":
        verts = [_pt(v.dxf.location, scale) for v in entity.vertices]
        bulges = [getattr(v.dxf, "bulge", 0.0) for v in entity.vertices]
        diags = []
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
# ARC / CIRCLE
# --------------------------------------------------------------------------- #
def _translate_circular(entity, dxftype, scale, layer, loc) -> TranslationResult:
    """ARC and CIRCLE, with the OCS→WCS correction their coordinates require.

    Three cases, decided by the extrusion vector:

    * **default (0,0,1)** — OCS is WCS. Nothing is touched, so drawings without
      an extrusion import exactly as they did before.
    * **mirrored (0,0,-1)** — still parallel to WCS XY, so the planar model can
      hold it exactly. The centre is transformed and, for an arc, the angles are
      mirrored with it.
    * **tilted (anything else)** — the circle genuinely does not lie in the XY
      plane. The centre is still corrected, but a planar Arc2D/Circle2D cannot
      express the plane, so ``OCS_TRANSFORM_FAILED`` says so rather than
      returning a confidently flat answer.
    """
    diags: List[GeometryDiagnostic] = []
    extrusion = _extrusion_of(entity)
    cx, cy, cz = _vec3(entity.dxf.center) or (0.0, 0.0, 0.0)
    radius = float(entity.dxf.radius) * scale

    if _uses_ocs(entity, dxftype):
        to_wcs = _wcs_mapper(entity)
        if to_wcs is not None:
            mapped = to_wcs(cx, cy, cz)
            if mapped is None:
                diags.append(diag.warning(
                    diag.OCS_TRANSFORM_FAILED,
                    "Could not map the entity's centre out of its object "
                    "coordinate system; coordinates are left untransformed.",
                    **loc))
            else:
                cx, cy, cz = mapped

        if not _is_planar_extrusion(extrusion):
            diags.append(diag.warning(
                diag.OCS_TRANSFORM_FAILED,
                f"Extrusion {tuple(round(v, 6) for v in extrusion)} tilts this "
                f"{dxftype.lower()} out of the XY plane; the centre is corrected "
                "but the neutral planar model cannot represent the plane itself.",
                **loc))

    center = Point(cx * scale, cy * scale, cz * scale)
    if abs(radius) <= _DEGENERATE_EPS_MM:
        diags.append(diag.warning(
            diag.ZERO_RADIUS, f"{dxftype.title()} has zero radius.", **loc))

    normal = None if _is_default_extrusion(extrusion) else Point(*extrusion)

    if dxftype == "CIRCLE":
        return Circle2D(center=center, radius=radius, layer=layer,
                        extrusion=normal), diags

    start = float(entity.dxf.start_angle)
    end = float(entity.dxf.end_angle)
    # A (0,0,-1) extrusion mirrors the plane, so the sweep must be mirrored too.
    if extrusion[2] < 0 and _is_planar_extrusion(extrusion):
        start, end = _mirror_arc_angles(start, end)

    return (
        Arc2D(center=center, radius=radius, start_angle=start, end_angle=end,
              layer=layer, extrusion=normal),
        diags,
    )


# --------------------------------------------------------------------------- #
# SPLINE
# --------------------------------------------------------------------------- #
# DXF SPLINE flag bits (group code 70).
_SPLINE_CLOSED = 1
_SPLINE_PERIODIC = 2
_SPLINE_RATIONAL = 4


def _floats(values) -> List[float]:
    """A plain float list from any sequence-like, unscaled.

    Knots live in parameter space and weights are dimensionless: neither is a
    length, so neither is multiplied by the unit scale.
    """
    return [float(v) for v in (values or [])]


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

    # Weights are positional — weight[i] belongs to control_points[i]. A count
    # mismatch makes that mapping unrecoverable, so they cannot be preserved.
    if weights and len(weights) != len(ctrl):
        diags.append(diag.loss(
            diag.RATIONAL_SPLINE_WEIGHTS_DROPPED,
            f"Spline has {len(weights)} weight(s) for {len(ctrl)} control "
            "point(s); the association is unrecoverable, so weights were dropped.",
            recoverable=False,
            metadata={"weight_count": len(weights),
                      "control_point_count": len(ctrl),
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
