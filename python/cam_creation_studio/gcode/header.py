"""Program header construction.

Two entry points, one source of truth:

* :func:`header_lines` turns a typed :class:`ProgramHeader` into ``Line`` objects
  (the object path).
* :func:`build_header` is the dict adapter — it maps a legacy ``config`` mapping
  onto a ``ProgramHeader`` and renders it to strings, preserving the exact output
  the prototype produced.

The header sets units and positioning, optionally homes, runs the dialect's
startup lines, then rapids to a safe Z.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from ..enums import Units
from ..models import ProgramHeader
from ..shared.numbers import parse_number_or_none
from .dialects import LineSpec, get_dialect
from .formatter import render
from .words import Line


def _safe_z(value: Any) -> float:
    z = parse_number_or_none(value)
    return 0 if z is None else z


def header_from_config(config: Mapping[str, Any]) -> ProgramHeader:
    """Map a legacy ``config`` mapping onto a typed :class:`ProgramHeader`."""
    return ProgramHeader(
        units=Units.INCH if config.get("units") == "in" else Units.MM,
        absolute=config.get("positioning") != "rel",
        home=bool(config.get("home")),
        machine=config.get("machine"),
        safe_z=_safe_z(config.get("safeZ")),
        spindle_on=bool(config.get("spindleOn")),
        spindle_rpm=parse_number_or_none(config.get("spindleRpm")),
        hotend_c=parse_number_or_none(config.get("hotend")),
        bed_c=parse_number_or_none(config.get("bed")),
    )


def _dialect_config(header: ProgramHeader) -> dict:
    """The subset a dialect's header/footer hooks read, drawn from the header."""
    return {
        "spindleOn": header.spindle_on,
        "spindleRpm": header.spindle_rpm,
        "hotend": header.hotend_c,
        "bed": header.bed_c,
    }


def _extra_to_line(spec: LineSpec) -> Line:
    return Line.of(spec.cmd, spec.words, spec.comment)


def header_lines(header: ProgramHeader) -> List[Line]:
    """Build the header as a list of :class:`Line` objects."""
    dialect = get_dialect(header.machine)
    lines: List[Line] = [Line(comment="--- HEADER ---")]

    if header.units is Units.INCH:
        lines.append(Line.of("G20", comment="units = inch"))
    else:
        lines.append(Line.of("G21", comment="units = mm"))

    if header.absolute:
        lines.append(Line.of("G90", comment="absolute positioning"))
    else:
        lines.append(Line.of("G91", comment="relative positioning"))

    if header.home:
        lines.append(Line.of("G28", comment="home all axes"))

    cfg = _dialect_config(header)
    for extra in dialect.header_extras(cfg):
        lines.append(_extra_to_line(extra))

    lines.append(Line.of("G0", {"Z": header.safe_z}, "move to safe height"))
    return lines


def build_header(config: Mapping[str, Any]) -> List[str]:
    """units, positioning, optional home, dialect startup, rapid to safe Z."""
    return [render(line) for line in header_lines(header_from_config(config))]
