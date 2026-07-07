"""Program footer construction.

Retract to a safe Z, run the dialect's shutdown lines (spindle/beam off, heaters
off), park at the origin, and end the program. :func:`footer_lines` is the object
path; :func:`build_footer` is the dict adapter that preserves prototype output.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from ..enums import Units
from ..models import ProgramFooter
from ..shared.numbers import parse_number_or_none
from .dialects import LineSpec, get_dialect
from .formatter import render
from .words import Line


def _safe_z(value: Any) -> float:
    z = parse_number_or_none(value)
    return 0 if z is None else z


def footer_from_config(config: Mapping[str, Any]) -> ProgramFooter:
    """Map a legacy ``config`` mapping onto a typed :class:`ProgramFooter`."""
    return ProgramFooter(
        units=Units.INCH if config.get("units") == "in" else Units.MM,
        machine=config.get("machine"),
        safe_z=_safe_z(config.get("safeZ")),
        spindle_on=bool(config.get("spindleOn")),
        hotend_c=parse_number_or_none(config.get("hotend")),
        bed_c=parse_number_or_none(config.get("bed")),
    )


def _dialect_config(footer: ProgramFooter) -> dict:
    return {
        "spindleOn": footer.spindle_on,
        "hotend": footer.hotend_c,
        "bed": footer.bed_c,
    }


def _extra_to_line(spec: LineSpec) -> Line:
    return Line.of(spec.cmd, spec.words, spec.comment)


def footer_lines(footer: ProgramFooter) -> List[Line]:
    """Build the footer as a list of :class:`Line` objects."""
    dialect = get_dialect(footer.machine)
    lines: List[Line] = [Line(comment="--- FOOTER ---")]
    lines.append(Line.of("G0", {"Z": footer.safe_z}, "retract"))
    for extra in dialect.footer_extras(_dialect_config(footer)):
        lines.append(_extra_to_line(extra))
    if footer.park:
        lines.append(Line.of("G0", {"X": 0, "Y": 0}, "park"))
    lines.append(Line.of(footer.end_code, comment="end of program"))
    return lines


def build_footer(config: Mapping[str, Any]) -> List[str]:
    """retract to safe Z, dialect shutdown, park at origin, end the program."""
    return [render(line) for line in footer_lines(footer_from_config(config))]
