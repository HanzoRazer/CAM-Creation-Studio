"""Deterministic bounds math for imported geometry (CS-008).

The tricky case is a circular arc: its bounding box is *not* just the box of its
endpoints, because the arc can bulge past them at the cardinal directions
(0 degrees = +X, 90 = +Y, 180 = -X, 270 = -Y). :func:`arc_extent` accounts for
whichever cardinals the sweep actually crosses.

These helpers operate on plain numbers and the shared :class:`Bounds`; they take
no dependency on the entity dataclasses, so ``models.py`` can consume them
without a circular import.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

from ..shared.geometry import Bounds, Point


def _normalize_deg(angle: float) -> float:
    """Fold an angle in degrees into ``[0, 360)``."""
    return angle % 360.0


def _angle_in_sweep(angle: float, start: float, end: float) -> bool:
    """Is ``angle`` within the CCW sweep from ``start`` to ``end`` (all degrees)?

    Matches the DXF ARC convention: arcs run counter-clockwise from ``start`` to
    ``end``. Endpoints are treated as inside the sweep.
    """
    a = _normalize_deg(angle)
    s = _normalize_deg(start)
    e = _normalize_deg(end)
    if math.isclose(s, e):
        # Zero or full sweep; ezdxf never emits a 360 arc, so treat as a point.
        return math.isclose(a, s)
    if s < e:
        return s <= a <= e
    # Sweep wraps through 0 degrees.
    return a >= s or a <= e


def arc_extent(
    cx: float,
    cy: float,
    radius: float,
    start_deg: float,
    end_deg: float,
) -> Tuple[float, float, float, float]:
    """Axis-aligned ``(min_x, min_y, max_x, max_y)`` of a CCW arc.

    Includes the two endpoints plus any of the four cardinal extreme points
    (+X, +Y, -X, -Y) that the sweep passes through.
    """
    sx = cx + radius * math.cos(math.radians(start_deg))
    sy = cy + radius * math.sin(math.radians(start_deg))
    ex = cx + radius * math.cos(math.radians(end_deg))
    ey = cy + radius * math.sin(math.radians(end_deg))

    xs = [sx, ex]
    ys = [sy, ey]
    # Cardinal candidates: angle -> (dx, dy) offset from center.
    cardinals = ((0.0, radius, 0.0), (90.0, 0.0, radius),
                 (180.0, -radius, 0.0), (270.0, 0.0, -radius))
    for angle, dx, dy in cardinals:
        if _angle_in_sweep(angle, start_deg, end_deg):
            xs.append(cx + dx)
            ys.append(cy + dy)
    return (min(xs), min(ys), max(xs), max(ys))


def from_extent(ext: Tuple[float, float, float, float]) -> Bounds:
    """Build a :class:`Bounds` from a 2D ``(min_x, min_y, max_x, max_y)`` tuple."""
    return Bounds(ext[0], ext[1], ext[2], ext[3])


def bounds_of_points(points: Sequence[Point]) -> Optional[Bounds]:
    """Planar bounds over ``points`` (z tracked), or ``None`` when empty."""
    pts = list(points)
    if not pts:
        return None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return Bounds(min(xs), min(ys), max(xs), max(ys), min(zs), max(zs))


def union(boxes: Iterable[Optional[Bounds]]) -> Optional[Bounds]:
    """Combine several :class:`Bounds` into one, skipping ``None``.

    Returns ``None`` when every input is ``None`` (nothing to bound).
    """
    present = [b for b in boxes if b is not None]
    if not present:
        return None
    return Bounds(
        min(b.min_x for b in present),
        min(b.min_y for b in present),
        max(b.max_x for b in present),
        max(b.max_y for b in present),
        min(b.min_z for b in present),
        max(b.max_z for b in present),
    )
