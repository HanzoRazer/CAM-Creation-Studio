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
splines keep only control points + degree (knot vectors, weights, and fit points
are dropped); ELLIPSE, TEXT, HATCH, DIMENSION, and INSERT/block references are
unsupported (:data:`~geometry.diagnostics.UNSUPPORTED_ENTITY`).
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

    if dxftype == "ARC":
        center = _pt(entity.dxf.center, scale)
        radius = float(entity.dxf.radius) * scale
        diags = []
        if abs(radius) <= _DEGENERATE_EPS_MM:
            diags.append(diag.warning(
                diag.ZERO_RADIUS, "Arc has zero radius.", **loc))
        return (
            Arc2D(
                center=center,
                radius=radius,
                start_angle=float(entity.dxf.start_angle),
                end_angle=float(entity.dxf.end_angle),
                layer=layer,
            ),
            diags,
        )

    if dxftype == "CIRCLE":
        center = _pt(entity.dxf.center, scale)
        radius = float(entity.dxf.radius) * scale
        diags = []
        if abs(radius) <= _DEGENERATE_EPS_MM:
            diags.append(diag.warning(
                diag.ZERO_RADIUS, "Circle has zero radius.", **loc))
        return Circle2D(center=center, radius=radius, layer=layer), diags

    if dxftype == "LWPOLYLINE":
        # "xyb" yields (x, y, bulge); a non-zero bulge is an arc we flatten to a
        # chord, so record it rather than change the shape silently.
        pts = list(entity.get_points("xyb"))
        verts = [Point(p[0] * scale, p[1] * scale) for p in pts]
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
        return Polyline2D(vertices=verts, closed=bool(entity.closed), layer=layer), diags

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
