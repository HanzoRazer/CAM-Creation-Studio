"""Vector-outline etch toolpaths.

Trace iso-contours of the darkness field at a threshold and chain them into
polylines. Ported from the prototype's genOutline. Output segments are neutral:
``{'poly': [{'x','y'}, ...]}``.
"""

from __future__ import annotations

from typing import Dict, List

from .field import DarknessField
from .marching_squares import chain_edges, marching_squares


def outline_etch(
    field: DarknessField,
    work_w: float,
    work_h: float,
    threshold: float = 0.55,
) -> List[Dict]:
    """Generate vector-outline paths at the given darkness threshold [0, 1]."""
    if field is None or field.gw < 2 or field.gh < 2:
        return []
    raw = marching_squares(field, work_w, work_h, threshold)
    return chain_edges(raw)
