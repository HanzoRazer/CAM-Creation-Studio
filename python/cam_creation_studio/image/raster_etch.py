"""Raster-fill etch toolpaths.

Boustrophedon (back-and-forth) scan lines over the darkness field; emit a burn
segment wherever darkness meets the threshold. Ported from the prototype's
genRaster. Output segments are neutral: ``{'poly': [{'x','y'}, {'x','y'}]}``.
"""

from __future__ import annotations

from typing import Dict, List

from .field import DarknessField, fit_rect


def raster_etch(
    field: DarknessField,
    work_w: float,
    work_h: float,
    line_spacing: float = 0.8,
    threshold: float = 0.55,
) -> List[Dict]:
    """Generate raster scan segments.

    :param threshold: darkness cutoff in [0, 1]; a pixel burns when its darkness
        is >= threshold.
    """
    if field is None or field.gw == 0:
        return []
    fr = fit_rect(field, work_w, work_h)
    sp = max(0.15, line_spacing or 0.8)
    th = threshold
    rows = max(1, round(fr.draw_h / sp))
    cols = max(2, round(fr.draw_w / sp))
    segs: List[Dict] = []

    for r in range(rows + 1):
        v = r / rows
        y_mm = fr.off_y + fr.draw_h - r * (fr.draw_h / rows)
        ltr = (r % 2) == 0
        start = None
        last_x = None
        for c in range(cols + 1):
            u = (c / cols) if ltr else (1 - c / cols)
            x_mm = fr.off_x + u * fr.draw_w
            on = field.darkness_at(u, v) >= th
            if on and start is None:
                start = x_mm
            if start is not None and (not on or c == cols):
                end_x = last_x if last_x is not None else x_mm
                segs.append({"poly": [{"x": start, "y": y_mm}, {"x": end_x, "y": y_mm}]})
                start = None
            if on:
                last_x = x_mm

    return segs
