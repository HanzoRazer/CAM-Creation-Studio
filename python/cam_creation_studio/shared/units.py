"""Unit conversion and normalization helpers. Units stay explicit everywhere."""

from __future__ import annotations

from typing import Any, Optional

from .numbers import parse_number_or_none, round_for_gcode

MM_PER_INCH = 25.4


def mm_to_in(mm: float) -> float:
    return mm / MM_PER_INCH


def in_to_mm(inch: float) -> float:
    return inch * MM_PER_INCH


def normalize_units(value: float, frm: str, to: str) -> float:
    """Convert ``value`` from ``frm`` units to ``to`` units ('mm' | 'in')."""
    if frm == to:
        return value
    if frm == "in" and to == "mm":
        return in_to_mm(value)
    if frm == "mm" and to == "in":
        return mm_to_in(value)
    raise ValueError(f"normalize_units: unsupported units {frm} -> {to}")


def format_unit_value(value: Any, units: str, decimals: Optional[int] = None) -> str:
    """Format a numeric value with its unit suffix, or '' if unparseable."""
    n = parse_number_or_none(value)
    if n is None:
        return ""
    if decimals is None:
        decimals = 4 if units == "in" else 3
    return f"{round_for_gcode(n, decimals)} {units}"


def units_code(units: str) -> str:
    """The G-code word that declares these units: G21 (mm) or G20 (inch)."""
    return "G20" if units == "in" else "G21"
