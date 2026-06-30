"""Pure G-code generation.

Ported from the browser prototype's buildManualGcode/buildEtchGcode, as
composable functions that take plain dict-like config + job objects:

    build_header(config)            -> list[str]
    build_manual_body(moves, config) -> list[str]
    build_etch_body(paths, config)  -> list[str]
    build_footer(config)            -> list[str]
    build_program(config, job)      -> str

Output is an EDUCATIONAL starting point. It is NOT a certified post-processor
and is NOT guaranteed safe to run. Always verify before use.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from ..shared.numbers import parse_number_or_none, round_for_gcode
from .dialects import LineSpec, get_dialect
from .formatter import format_line, section_line


def _render_extra(spec: LineSpec) -> str:
    return format_line(spec.cmd, spec.words, spec.comment)


def _safe_z(config: Mapping[str, Any]):
    z = parse_number_or_none(config.get("safeZ"))
    return 0 if z is None else z


def build_header(config: Mapping[str, Any]) -> List[str]:
    """units, positioning, optional home, dialect startup, rapid to safe Z."""
    dialect = get_dialect(config.get("machine"))
    lines = [section_line("HEADER")]

    if config.get("units") == "in":
        lines.append(format_line("G20", {}, "units = inch"))
    else:
        lines.append(format_line("G21", {}, "units = mm"))

    if config.get("positioning") == "rel":
        lines.append(format_line("G91", {}, "relative positioning"))
    else:
        lines.append(format_line("G90", {}, "absolute positioning"))

    if config.get("home"):
        lines.append(format_line("G28", {}, "home all axes"))

    for extra in dialect.header_extras(config):
        lines.append(_render_extra(extra))

    lines.append(format_line("G0", {"Z": _safe_z(config)}, "move to safe height"))
    return lines


def build_manual_body(moves: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> List[str]:
    """Manual-move body. Each move is a dict with type/x/y/z/f/e/i/j fields."""
    dialect = get_dialect(config.get("machine"))
    is_marlin = dialect.id == "marlin"
    lines = [section_line("BODY")]

    for m in moves:
        move_type = m.get("type", "G1")
        is_arc = move_type in ("G2", "G3")
        words: dict = {"X": m.get("x", ""), "Y": m.get("y", ""), "Z": m.get("z", "")}
        if is_arc:
            words["I"] = m.get("i", "")
            words["J"] = m.get("j", "")
        if is_marlin:
            words["E"] = m.get("e", "")
        words["F"] = m.get("f", "")
        lines.append(format_line(move_type, words))
    return lines


def build_etch_body(paths: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> List[str]:
    """Image-etch body from neutral path segments ({'poly': [{'x','y'}, ...]}).

    control 'power': beam toggled per segment via M3 S / M5.
    control 'depth': plunge to engraveZ, cut, retract to safe Z.
    """
    etch = config.get("etch", {})
    power = etch.get("control") != "depth"
    feed = etch.get("feed", 600)
    s_power = etch.get("power", 200)
    engrave_z = etch.get("engraveZ", -0.2)
    z = _safe_z(config)

    def r(n):
        return round_for_gcode(n, 3)

    lines = [section_line("TOOLPATH")]
    if not paths:
        lines.append("; (no burn regions — load an image or lower the cutoff)")
        return lines

    for seg in paths:
        poly = seg["poly"]
        a = poly[0]
        if power:
            lines.append(format_line("G0", {"X": r(a["x"]), "Y": r(a["y"])}))
            lines.append(format_line("M3", {"S": s_power}))
        else:
            lines.append(format_line("G0", {"Z": z}))
            lines.append(format_line("G0", {"X": r(a["x"]), "Y": r(a["y"])}))
            lines.append(format_line("G1", {"Z": engrave_z, "F": 300}))
        for k in range(1, len(poly)):
            p = poly[k]
            words = {"X": r(p["x"]), "Y": r(p["y"])}
            if k == 1:
                words["F"] = feed
            lines.append(format_line("G1", words))
        lines.append(format_line("M5") if power else format_line("G0", {"Z": z}))
    return lines


def build_footer(config: Mapping[str, Any]) -> List[str]:
    """retract to safe Z, dialect shutdown, park at origin, end the program."""
    dialect = get_dialect(config.get("machine"))
    lines = [section_line("FOOTER")]
    lines.append(format_line("G0", {"Z": _safe_z(config)}, "retract"))
    for extra in dialect.footer_extras(config):
        lines.append(_render_extra(extra))
    lines.append(format_line("G0", {"X": 0, "Y": 0}, "park"))
    lines.append(format_line("M30", {}, "end of program"))
    return lines


def build_program(config: Mapping[str, Any], job: Mapping[str, Any]) -> str:
    """Assemble a complete program from a config + a job.

    job = {"mode": "manual", "moves": [...]}
    job = {"mode": "etch",   "paths": [...]}   (etch settings on config['etch'])
    """
    if job.get("mode") == "etch":
        body = build_etch_body(job.get("paths", []), config)
    else:
        body = build_manual_body(job.get("moves", []), config)

    return "\n".join([*build_header(config), "", *body, "", *build_footer(config)])
