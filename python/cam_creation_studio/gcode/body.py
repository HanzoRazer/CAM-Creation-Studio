"""Program body construction.

The body is the sequence of motion instructions between header and footer. Two
kinds of body exist:

* manual moves — a list of :class:`~cam_creation_studio.models.Move` /
  :class:`~cam_creation_studio.models.ArcMove` (or their legacy dict form), and
* image-etch paths — neutral polylines burned or engraved segment by segment.

:func:`body_lines_from_moves` is the object path; :func:`build_manual_body` and
:func:`build_etch_body` are the dict adapters that preserve the prototype output.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from ..models import AnyMove
from ..shared.numbers import parse_number_or_none, round_for_gcode
from .formatter import render, section_line
from .words import Line

# Word emission order on a motion line: coordinates, arc center, extrusion, feed.


def _safe_z(config: Mapping[str, Any]) -> float:
    z = parse_number_or_none(config.get("safeZ"))
    return 0 if z is None else z


def body_lines_from_moves(moves: Sequence[AnyMove], is_marlin: bool = False) -> List[Line]:
    """Build body :class:`Line` objects from typed Move/ArcMove instructions."""
    lines: List[Line] = [Line(comment="--- BODY ---")]
    for m in moves:
        words: dict = {"X": m.x, "Y": m.y, "Z": m.z}
        if m.is_arc:
            words["I"] = m.i
            words["J"] = m.j
        elif is_marlin:
            words["E"] = m.e
        words["F"] = m.feed
        lines.append(Line.of(m.type.value, words, getattr(m, "comment", "")))
    return lines


def build_manual_body(moves: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> List[str]:
    """Manual-move body (dict adapter). Each move is a dict with type/x/y/z/f/e/i/j."""
    from .dialects import get_dialect

    is_marlin = get_dialect(config.get("machine")).id == "marlin"
    lines: List[str] = [section_line("BODY")]

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
        lines.append(render(Line.of(move_type, words)))
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

    lines: List[str] = [section_line("TOOLPATH")]
    if not paths:
        lines.append("; (no burn regions — load an image or lower the cutoff)")
        return lines

    for seg in paths:
        poly = seg["poly"]
        a = poly[0]
        if power:
            lines.append(render(Line.of("G0", {"X": r(a["x"]), "Y": r(a["y"])})))
            lines.append(render(Line.of("M3", {"S": s_power})))
        else:
            lines.append(render(Line.of("G0", {"Z": z})))
            lines.append(render(Line.of("G0", {"X": r(a["x"]), "Y": r(a["y"])})))
            lines.append(render(Line.of("G1", {"Z": engrave_z, "F": 300})))
        for k in range(1, len(poly)):
            p = poly[k]
            words = {"X": r(p["x"]), "Y": r(p["y"])}
            if k == 1:
                words["F"] = feed
            lines.append(render(Line.of("G1", words)))
        lines.append(render(Line.of("M5")) if power else render(Line.of("G0", {"Z": z})))
    return lines
