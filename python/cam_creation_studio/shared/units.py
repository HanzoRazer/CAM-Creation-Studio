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


# --------------------------------------------------------------------------- #
# DXF unit normalization (CS-008)
#
# A DXF header carries ``$INSUNITS``, an integer enumerating the drawing's
# insertion units. We normalize all imported geometry to millimetres and keep
# the original unit *name* as import metadata. The table below maps the codes we
# recognize to (human name, scale-to-mm). Codes outside the table are treated as
# unknown by the importer, which records a diagnostic and assumes a 1.0 scale.
#
# Codes follow the AutoCAD DXF ``$INSUNITS`` enumeration exactly — getting them
# wrong silently rescales the whole drawing. In particular code 8 is *microinches*
# (not microns, which is code 13) and code 9 is *mils* = 0.001 inch (not a
# millimetre variant). A drawing authored in mils imported at 1:1 mm would be off
# by ~39x, so these are correctness-critical, not cosmetic.
# --------------------------------------------------------------------------- #
DXF_INSUNITS: dict[int, tuple[str, float]] = {
    0: ("unitless", 1.0),
    1: ("in", MM_PER_INCH),
    2: ("ft", MM_PER_INCH * 12.0),
    3: ("mi", MM_PER_INCH * 63360.0),
    4: ("mm", 1.0),
    5: ("cm", 10.0),
    6: ("m", 1000.0),
    7: ("km", 1_000_000.0),
    8: ("microinch", MM_PER_INCH * 1e-6),
    9: ("mil", MM_PER_INCH * 1e-3),          # mil = 0.001 inch
    10: ("yd", MM_PER_INCH * 36.0),
    13: ("micron", 0.001),
    14: ("dm", 100.0),
}


def dxf_units_name(insunits: Optional[int]) -> Optional[str]:
    """Human unit name for a DXF ``$INSUNITS`` code, or ``None`` if unrecognized."""
    if insunits is None:
        return None
    entry = DXF_INSUNITS.get(int(insunits))
    return entry[0] if entry else None


def dxf_scale_to_mm(insunits: Optional[int]) -> Optional[float]:
    """Scale factor to convert DXF ``$INSUNITS`` lengths to millimetres.

    Returns ``None`` for an unknown/absent code so the caller can raise a
    diagnostic and fall back to a 1.0 (identity) scale explicitly.
    """
    if insunits is None:
        return None
    entry = DXF_INSUNITS.get(int(insunits))
    return entry[1] if entry else None
