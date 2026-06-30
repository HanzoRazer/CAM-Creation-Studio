"""Marching squares contour extraction.

Walk each 2x2 cell of the darkness field and emit the iso-contour edge(s) at the
threshold, in millimetre work coordinates. Ported from the prototype's
genOutline inner loop. Returns raw edges as ``[(x0, y0), (x1, y1)]`` pairs; use
``chain_edges`` to join them into polylines.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .field import DarknessField, fit_rect

Point = Tuple[float, float]
Edge = Tuple[Point, Point]


def marching_squares(field: DarknessField, work_w: float, work_h: float,
                     threshold: float = 0.55) -> List[Edge]:
    gw, gh = field.gw, field.gh
    fr = fit_rect(field, work_w, work_h)
    th = threshold

    def val(x: int, y: int) -> float:
        return field.data[y * gw + x]

    def mm(gx: float, gy: float) -> Point:
        return (
            fr.off_x + (gx / (gw - 1)) * fr.draw_w,
            fr.off_y + (1 - gy / (gh - 1)) * fr.draw_h,
        )

    raw: List[Edge] = []
    for y in range(gh - 1):
        for x in range(gw - 1):
            tl, tr = val(x, y), val(x + 1, y)
            br, bl = val(x + 1, y + 1), val(x, y + 1)
            idx = 0
            if tl >= th:
                idx |= 8
            if tr >= th:
                idx |= 4
            if br >= th:
                idx |= 2
            if bl >= th:
                idx |= 1
            if idx in (0, 15):
                continue

            def it(a: float, b: float) -> float:
                return (th - a) / ((b - a) or 1e-6)

            top = lambda: mm(x + it(tl, tr), y)
            right = lambda: mm(x + 1, y + it(tr, br))
            bottom = lambda: mm(x + it(bl, br), y + 1)
            left = lambda: mm(x, y + it(tl, bl))

            if idx in (1, 14):
                raw.append((left(), bottom()))
            elif idx in (2, 13):
                raw.append((bottom(), right()))
            elif idx in (3, 12):
                raw.append((left(), right()))
            elif idx in (4, 11):
                raw.append((top(), right()))
            elif idx == 5:
                raw.append((left(), top()))
                raw.append((bottom(), right()))
            elif idx in (6, 9):
                raw.append((top(), bottom()))
            elif idx in (7, 8):
                raw.append((left(), top()))
            elif idx == 10:
                raw.append((top(), right()))
                raw.append((left(), bottom()))

    return raw


def chain_edges(raw: List[Edge]) -> List[Dict]:
    """Join raw edges into polylines. Returns ``[{'poly': [{'x','y'}, ...]}, ...]``."""

    def key(p: Point) -> str:
        return f"{round(p[0] * 50) / 50},{round(p[1] * 50) / 50}"

    used = [False] * len(raw)
    index: Dict[str, List[Tuple[int, int]]] = {}
    for i, seg in enumerate(raw):
        for e in (0, 1):
            index.setdefault(key(seg[e]), []).append((i, e))

    polys: List[Dict] = []
    for i in range(len(raw)):
        if used[i]:
            continue
        used[i] = True
        poly: List[Point] = [raw[i][0], raw[i][1]]

        grow = True
        while grow:
            grow = False
            for (ci, ce) in index.get(key(poly[-1]), []):
                if used[ci]:
                    continue
                poly.append(raw[ci][1 - ce])
                used[ci] = True
                grow = True
                break

        grow = True
        while grow:
            grow = False
            for (ci, ce) in index.get(key(poly[0]), []):
                if used[ci]:
                    continue
                poly.insert(0, raw[ci][1 - ce])
                used[ci] = True
                grow = True
                break

        polys.append({"poly": [{"x": p[0], "y": p[1]} for p in poly]})

    return polys
