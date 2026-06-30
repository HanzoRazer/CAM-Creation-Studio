"""Darkness field and work-area fitting.

A DarknessField is a grid of darkness values in [0, 1] (1 = fully dark / burn,
0 = white / skip), row-major. It is the neutral input both etch strategies
consume, decoupled from any specific image library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class FitRect:
    W: float
    H: float
    draw_w: float
    draw_h: float
    off_x: float
    off_y: float


@dataclass
class DarknessField:
    gw: int
    gh: int
    data: List[float]  # length gw*gh, row-major, values in [0, 1]

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[float]]) -> "DarknessField":
        """Build from a 2D grid of darkness values (rows of equal length)."""
        gh = len(rows)
        gw = len(rows[0]) if gh else 0
        data: List[float] = []
        for row in rows:
            if len(row) != gw:
                raise ValueError("All rows must have the same length.")
            data.extend(float(v) for v in row)
        return cls(gw=gw, gh=gh, data=data)

    @classmethod
    def from_luminance(cls, rows: Sequence[Sequence[float]], scale: float = 1.0) -> "DarknessField":
        """Build from luminance values in [0, 1] (1 = white). Darkness = 1 - lum."""
        inverted = [[1.0 - (v / scale) for v in row] for row in rows]
        return cls.from_rows(inverted)

    def value(self, x: int, y: int) -> float:
        return self.data[y * self.gw + x]

    def darkness_at(self, u: float, v: float) -> float:
        """Nearest-sample darkness at normalized coords u,v in [0, 1]."""
        gx = min(self.gw - 1, max(0, round(u * (self.gw - 1))))
        gy = min(self.gh - 1, max(0, round(v * (self.gh - 1))))
        return self.data[gy * self.gw + gx]


def fit_rect(field: DarknessField, work_w: float, work_h: float) -> FitRect:
    """Fit the field's aspect ratio into the work area, centered."""
    ar = (field.gw / field.gh) if field and field.gh else 1.0
    draw_w = work_w
    draw_h = work_w / ar
    if draw_h > work_h:
        draw_h = work_h
        draw_w = work_h * ar
    return FitRect(
        W=work_w,
        H=work_h,
        draw_w=draw_w,
        draw_h=draw_h,
        off_x=(work_w - draw_w) / 2,
        off_y=(work_h - draw_h) / 2,
    )
