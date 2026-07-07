"""Shared geometry primitives and pure helpers.

These are machine-independent building blocks: a :class:`Point`, an axis-aligned
:class:`Bounds`, and functions to measure distance, arc length, and to flatten an
arc into line segments. Higher layers (preview, future rendering) consume these
so the geometry lives in exactly one place.

Nothing here knows about G-code words or dialects — it is pure math on points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass(frozen=True, slots=True)
class Point:
    """An immutable point in machine space (millimetres by convention)."""

    x: float
    y: float
    z: float = 0.0

    def distance_to(self, other: "Point") -> float:
        return distance(self, other)


@dataclass(frozen=True, slots=True)
class Bounds:
    """An axis-aligned bounding box. ``z`` extents are tracked but optional."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    min_z: float = 0.0
    max_z: float = 0.0

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def depth(self) -> float:
        return self.max_z - self.min_z

    @property
    def center(self) -> Point:
        return Point(
            (self.min_x + self.max_x) / 2.0,
            (self.min_y + self.max_y) / 2.0,
            (self.min_z + self.max_z) / 2.0,
        )

    def as_tuple(self) -> tuple:
        """(min_x, min_y, max_x, max_y) — the 2D box, for renderers/tests."""
        return (self.min_x, self.min_y, self.max_x, self.max_y)


def distance(a: Point, b: Point) -> float:
    """Straight-line 3D distance between two points."""
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2)


def distance_2d(a: Point, b: Point) -> float:
    """Planar (XY) distance between two points, ignoring Z."""
    return math.hypot(b.x - a.x, b.y - a.y)


def arc_length(radius: float, sweep_radians: float) -> float:
    """Length of a circular arc of ``radius`` swept through ``sweep_radians``.

    ``sweep_radians`` may be signed; the returned length is always non-negative.
    """
    return abs(radius) * abs(sweep_radians)


def bounds(points: Sequence[Point]) -> Optional[Bounds]:
    """Axis-aligned bounds over ``points``, or ``None`` when the sequence is empty."""
    pts = list(points)
    if not pts:
        return None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return Bounds(min(xs), min(ys), max(xs), max(ys), min(zs), max(zs))


def _arc_sweep(a0: float, a1: float, clockwise: bool) -> float:
    """Signed angular sweep from ``a0`` to ``a1`` in the given direction."""
    d = a1 - a0
    if clockwise:
        if d >= 0:
            d -= 2 * math.pi
    else:
        if d <= 0:
            d += 2 * math.pi
    return d


def interpolate_arc(
    start: Point,
    end: Point,
    i: float,
    j: float,
    clockwise: bool,
    segments: int = 40,
) -> List[Point]:
    """Flatten a G2/G3 arc into a polyline of ``Point``.

    ``i``/``j`` are the center offsets from ``start`` (G-code I/J convention).
    Returns ``[start, ..., end]`` with ``segments`` subdivisions; ``z`` is
    linearly interpolated from ``start.z`` to ``end.z`` along the sweep.
    """
    if segments < 1:
        segments = 1
    cx, cy = start.x + i, start.y + j
    radius = math.hypot(start.x - cx, start.y - cy)
    a0 = math.atan2(start.y - cy, start.x - cx)
    a1 = math.atan2(end.y - cy, end.x - cx)
    sweep = _arc_sweep(a0, a1, clockwise)

    points = [start]
    for k in range(1, segments + 1):
        t = k / segments
        a = a0 + sweep * t
        px = cx + radius * math.cos(a)
        py = cy + radius * math.sin(a)
        pz = start.z + (end.z - start.z) * t
        points.append(Point(px, py, pz))
    return points


# --------------------------------------------------------------------------- #
# Spec-canonical names (CS-003). The functions above are the implementation;
# these aliases expose the names the domain contract promises. Both are public.
# --------------------------------------------------------------------------- #
distance_3d = distance                 # explicit 3D distance
arc_points = interpolate_arc           # flatten an arc into points
bounds_from_points = bounds            # axis-aligned bounds over points

__all__ = [
    "Point",
    "Bounds",
    "distance",
    "distance_2d",
    "distance_3d",
    "arc_length",
    "bounds",
    "bounds_from_points",
    "interpolate_arc",
    "arc_points",
]
