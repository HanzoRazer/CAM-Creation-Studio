"""Neutral preview model.

Convert manual moves and etch paths into renderer-agnostic segments. A renderer
(canvas, matplotlib, SVG, ...) consumes these without knowing about G-code.

Segment:
    type:  'travel' | 'cut' | 'burn'
    frm:   Point(x, y, z)
    to:    Point(x, y, z)
    feed:  Optional[float]
    source_line: Optional[int]   (index of the originating move)

This is a MODEL, not a simulation: it does not consider tool geometry,
material, or collisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence

from ..shared.numbers import parse_number_or_none

TRAVEL = "travel"
CUT = "cut"
BURN = "burn"

_ARC_STEPS = 40


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class Segment:
    type: str
    frm: Point
    to: Point
    feed: Optional[float] = None
    source_line: Optional[int] = None


def _num(value, fallback):
    n = parse_number_or_none(value)
    return fallback if n is None else n


def model_from_moves(moves: Sequence[Mapping], laser: bool = False) -> List[Segment]:
    """Build segments from manual moves.

    G0 -> travel. G1/G2/G3 -> 'burn' when ``laser`` else 'cut'. Arcs (G2/G3
    with I/J) are flattened into short segments.
    """
    segs: List[Segment] = []
    cur = Point(0.0, 0.0, 0.0)
    feed: Optional[float] = None

    for idx, m in enumerate(moves):
        mtype = m.get("type", "G1")
        tx = _num(m.get("x"), cur.x)
        ty = _num(m.get("y"), cur.y)
        tz = _num(m.get("z"), cur.z)
        f = parse_number_or_none(m.get("f"))
        if f is not None:
            feed = f

        if mtype in ("G2", "G3"):
            i = parse_number_or_none(m.get("i"))
            j = parse_number_or_none(m.get("j"))
            if i is not None and j is not None:
                cur = _emit_arc(segs, cur, Point(tx, ty, tz), i, j, mtype, feed, idx, laser)
                continue

        seg_type = TRAVEL if mtype == "G0" else (BURN if laser else CUT)
        to = Point(tx, ty, tz)
        segs.append(Segment(seg_type, cur, to, None if seg_type == TRAVEL else feed, idx))
        cur = to

    return segs


def _emit_arc(segs, start: Point, end: Point, i: float, j: float, mtype: str,
              feed, idx: int, laser: bool) -> Point:
    cx, cy = start.x + i, start.y + j
    rad = math.hypot(start.x - cx, start.y - cy)
    a0 = math.atan2(start.y - cy, start.x - cx)
    a1 = math.atan2(end.y - cy, end.x - cx)
    d = a1 - a0
    if mtype == "G2":
        if d >= 0:
            d -= 2 * math.pi
    else:
        if d <= 0:
            d += 2 * math.pi

    seg_type = BURN if laser else CUT
    prev = start
    for k in range(1, _ARC_STEPS + 1):
        a = a0 + d * (k / _ARC_STEPS)
        px = cx + rad * math.cos(a)
        py = cy + rad * math.sin(a)
        pt = Point(px, py, end.z)
        segs.append(Segment(seg_type, prev, pt, feed, idx))
        prev = pt
    return Point(end.x, end.y, end.z)


def model_from_etch_paths(paths: Sequence[Mapping], control: str = "power",
                          feed: Optional[float] = None) -> List[Segment]:
    """Build segments from neutral etch paths ({'poly': [{'x','y'}, ...]}).

    Travel segments connect the end of one path to the start of the next; the
    path itself is 'burn' (power control) or 'cut' (depth control).
    """
    seg_type = BURN if control != "depth" else CUT
    segs: List[Segment] = []
    prev_end: Optional[Point] = None

    for idx, path in enumerate(paths):
        poly = path["poly"]
        if not poly:
            continue
        start = Point(poly[0]["x"], poly[0]["y"], 0.0)
        if prev_end is not None:
            segs.append(Segment(TRAVEL, prev_end, start, None, idx))
        for k in range(1, len(poly)):
            a = Point(poly[k - 1]["x"], poly[k - 1]["y"], 0.0)
            b = Point(poly[k]["x"], poly[k]["y"], 0.0)
            segs.append(Segment(seg_type, a, b, feed, idx))
        prev_end = Point(poly[-1]["x"], poly[-1]["y"], 0.0)

    return segs


def bounds(segments: Sequence[Segment]):
    """Return (min_x, min_y, max_x, max_y) over all segment endpoints, or None."""
    xs: List[float] = []
    ys: List[float] = []
    for s in segments:
        xs.extend([s.frm.x, s.to.x])
        ys.extend([s.frm.y, s.to.y])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))
