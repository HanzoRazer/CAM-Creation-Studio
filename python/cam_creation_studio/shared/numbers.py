"""Numeric sanitizers and math helpers shared across the core.

All helpers are pure. This module also owns the small reusable math utilities
(``clamp``, ``lerp``, ``round_gcode``, ``normalize_angle``) — the core keeps a
single home for numeric responsibility rather than a separate ``mathutils``.
"""

from __future__ import annotations

import math
from typing import Any, Optional


def parse_number_or_none(value: Any) -> Optional[float]:
    """Parse a value into a float, or return ``None`` when it cannot be parsed.

    Empty strings, ``None``, and non-numeric strings all collapse to ``None``.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bools are ints in Python
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp_number(n: float, low: float, high: float) -> float:
    """Clamp ``n`` into the inclusive ``[low, high]`` range."""
    if n < low:
        return low
    if n > high:
        return high
    return n


def round_for_gcode(n: float, decimals: int = 3) -> float:
    """Round to a fixed precision and drop the ``.0`` so ``10.0`` prints as ``10``.

    Returns an ``int`` when the result is integral, otherwise a ``float``.
    """
    if n is None:
        return 0
    rounded = round(float(n), decimals)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def is_positive_number(value: Any) -> bool:
    """True when ``value`` parses to a number strictly greater than zero."""
    n = parse_number_or_none(value)
    return n is not None and n > 0


def format_number(n: float, decimals: int = 3) -> str:
    """Format a number for G-code output: rounded, no trailing ``.0``."""
    return str(round_for_gcode(n, decimals))


# --- reusable math utilities (mathutils responsibility lives here) ---

def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from ``a`` to ``b`` by fraction ``t``.

    ``t`` is not clamped: ``t=0`` -> ``a``, ``t=1`` -> ``b``, and values outside
    ``[0, 1]`` extrapolate.
    """
    return a + (b - a) * t


def normalize_angle(radians: float) -> float:
    """Wrap an angle (radians) into the half-open range ``[-pi, pi)``."""
    two_pi = 2.0 * math.pi
    wrapped = (radians + math.pi) % two_pi
    return wrapped - math.pi


# Short aliases matching the domain-facing vocabulary. ``clamp`` and
# ``round_gcode`` are the canonical names used by the geometry/model layer;
# the longer originals remain for existing callers.
clamp = clamp_number
round_gcode = round_for_gcode
