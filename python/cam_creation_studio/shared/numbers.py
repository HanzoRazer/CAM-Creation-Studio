"""Numeric sanitizers shared across the core. All helpers are pure."""

from __future__ import annotations

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
