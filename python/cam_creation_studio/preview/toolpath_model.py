"""Neutral preview model.

Convert manual moves and etch paths into renderer-agnostic segments. A renderer
(canvas, matplotlib, SVG, ...) consumes these without knowing about G-code.

Segment:
    type:  'travel' | 'cut' | 'burn'
    frm:   Point(x, y, z)
    to:    Point(x, y, z)
    feed:  Optional[float]
    source_line: Optional[int]   (index of the originating move)

This is a MODEL, not a simulation: it does not consider tool geometry,
material, or collisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from ..shared import geometry as geom
from ..shared.numbers import parse_number_or_none

TRAVEL = "travel"
CUT = "cut"
BURN = "burn"
EXTRUDE = "extrude"
ARC = "arc"

_ARC_STEPS = 40
# A chord may legitimately equal 2*R (a semicircle); this relative slack lets
# float drift past 2*R still count as a semicircle rather than "impossible".
_ARC_CHORD_TOL = 1e-9

# Intent markers that mark a raw program as a laser/beam ('burn') job when no
# machine profile is available to say so. Matched only inside comments.
_BURN_TEXT_MARKERS = ("laser", "beam", "burn")

# Laser/power dialects: on these, a feed move marks material by beam power, so
# the canonical model classifies it as a burn segment rather than a cut.
_LASER_MACHINES = {"laser", "laserGrbl"}


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class Segment:
    type: str
    frm: Point
    to: Point
    feed: Optional[float] = None
    source_line: Optional[int] = None


@dataclass(frozen=True)
class ToolpathSegment:
    """A richer, renderer-agnostic motion segment (CS-003 canonical shape).

    Unlike :class:`Segment` (a minimal from/to pair), this carries everything a
    future renderer, report, or inspector needs without re-deriving it:

      type            'travel' | 'cut' | 'extrude' | 'arc' | 'burn'
      start / end     Point(x, y, z) endpoints
      feed            F word in effect (mm/min), or None for travel
      z               end-point Z (convenience; == end.z)
      line            originating source line/index (1-based)
      source_command  the G-word that produced it ('G0'..'G3')
      distance        segment length in mm (arc length for arcs)

    ``frm``/``to``/``source_line`` properties mirror :class:`Segment` so the two
    are interchangeable to consumers that only read endpoints.
    """

    type: str
    start: Point
    end: Point
    feed: Optional[float] = None
    z: float = 0.0
    line: Optional[int] = None
    source_command: str = ""
    distance: float = 0.0

    @property
    def frm(self) -> Point:
        return self.start

    @property
    def to(self) -> Point:
        return self.end

    @property
    def source_line(self) -> Optional[int]:
        return self.line


def _num(value, fallback):
    n = parse_number_or_none(value)
    return fallback if n is None else n


def model_from_moves(moves: Sequence[Mapping], laser: bool = False) -> List[Segment]:
    """Build segments from manual moves.

    G0 -> travel. G1/G2/G3 -> 'burn' when ``laser`` else 'cut'. Arcs (G2/G3
    with I/J) are flattened into short segments.
    """
    segs: List[Segment] = []
    cur = Point(0.0, 0.0, 0.0)
    feed: Optional[float] = None

    for idx, m in enumerate(moves):
        mtype = m.get("type", "G1")
        tx = _num(m.get("x"), cur.x)
        ty = _num(m.get("y"), cur.y)
        tz = _num(m.get("z"), cur.z)
        f = parse_number_or_none(m.get("f"))
        if f is not None:
            feed = f

        if mtype in ("G2", "G3"):
            i = parse_number_or_none(m.get("i"))
            j = parse_number_or_none(m.get("j"))
            if i is not None and j is not None:
                cur = _emit_arc(segs, cur, Point(tx, ty, tz), i, j, mtype, feed, idx, laser)
                continue

        seg_type = TRAVEL if mtype == "G0" else (BURN if laser else CUT)
        to = Point(tx, ty, tz)
        segs.append(Segment(seg_type, cur, to, None if seg_type == TRAVEL else feed, idx))
        cur = to

    return segs


def _signed_sweep(a0: float, a1: float, clockwise: bool) -> float:
    """Swept angle from ``a0`` to ``a1`` respecting the arc direction.

    ``G2`` (``clockwise``) sweeps the negative direction, ``G3`` the positive
    one. A zero raw difference (coincident start/end) becomes a full ``2*pi``
    turn in the given direction. This is the single source of truth for arc
    direction, shared by the flattener and the distance estimate so the two
    cannot drift apart.
    """
    sweep = a1 - a0
    if clockwise:
        if sweep >= 0:
            sweep -= 2 * math.pi
    else:
        if sweep <= 0:
            sweep += 2 * math.pi
    return sweep


def _emit_arc(segs, start: Point, end: Point, i: float, j: float, mtype: str,
              feed, idx: int, laser: bool) -> Point:
    cx, cy = start.x + i, start.y + j
    rad = math.hypot(start.x - cx, start.y - cy)
    a0 = math.atan2(start.y - cy, start.x - cx)
    a1 = math.atan2(end.y - cy, end.x - cx)
    d = _signed_sweep(a0, a1, mtype == "G2")

    seg_type = BURN if laser else CUT
    prev = start
    for k in range(1, _ARC_STEPS + 1):
        a = a0 + d * (k / _ARC_STEPS)
        px = cx + rad * math.cos(a)
        py = cy + rad * math.sin(a)
        pt = Point(px, py, end.z)
        segs.append(Segment(seg_type, prev, pt, feed, idx))
        prev = pt
    return Point(end.x, end.y, end.z)


def model_from_etch_paths(paths: Sequence[Mapping], control: str = "power",
                          feed: Optional[float] = None) -> List[Segment]:
    """Build segments from neutral etch paths ({'poly': [{'x','y'}, ...]}).

    Travel segments connect the end of one path to the start of the next; the
    path itself is 'burn' (power control) or 'cut' (depth control).
    """
    seg_type = BURN if control != "depth" else CUT
    segs: List[Segment] = []
    prev_end: Optional[Point] = None

    for idx, path in enumerate(paths):
        poly = path["poly"]
        if not poly:
            continue
        start = Point(poly[0]["x"], poly[0]["y"], 0.0)
        if prev_end is not None:
            segs.append(Segment(TRAVEL, prev_end, start, None, idx))
        for k in range(1, len(poly)):
            a = Point(poly[k - 1]["x"], poly[k - 1]["y"], 0.0)
            b = Point(poly[k]["x"], poly[k]["y"], 0.0)
            segs.append(Segment(seg_type, a, b, feed, idx))
        prev_end = Point(poly[-1]["x"], poly[-1]["y"], 0.0)

    return segs


def bounds(segments: Sequence) -> Optional[tuple]:
    """Return (min_x, min_y, max_x, max_y) over all segment endpoints, or None.

    Accepts :class:`Segment` or :class:`ToolpathSegment` (both expose frm/to).
    """
    xs: List[float] = []
    ys: List[float] = []
    for s in segments:
        xs.extend([s.frm.x, s.to.x])
        ys.extend([s.frm.y, s.to.y])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------- #
# Canonical bridge: parsed program -> ToolpathSegment list (CS-003)
# --------------------------------------------------------------------------- #
def _normalize_move(item: Any, index: int) -> Optional[dict]:
    """Coerce one parsed element into a flat move dict, or None if not motion.

    Accepts domain moves (Move/ArcMove), ParsedLine, or a plain mapping.
    """
    # Domain Move / ArcMove (have a MoveType ``type`` and axis attributes).
    mtype = getattr(item, "type", None)
    if mtype is not None and hasattr(mtype, "value") and not isinstance(item, Mapping):
        cmd = mtype.value
        if cmd not in ("G0", "G1", "G2", "G3"):
            return None
        return {
            "cmd": cmd,
            "x": getattr(item, "x", None), "y": getattr(item, "y", None),
            "z": getattr(item, "z", None), "f": getattr(item, "feed", None),
            "e": getattr(item, "e", None), "i": getattr(item, "i", None),
            "j": getattr(item, "j", None), "r": getattr(item, "r", None),
            "line": getattr(item, "line", None) or (index + 1),
        }

    # ParsedLine (lexical view): has a ``motion`` property and word()/number.
    if hasattr(item, "motion") and hasattr(item, "word"):
        cmd = item.motion
        if cmd is None:
            return None
        return {
            "cmd": cmd,
            "x": item.word("X"), "y": item.word("Y"), "z": item.word("Z"),
            "f": item.word("F"), "e": item.word("E"),
            "i": item.word("I"), "j": item.word("J"), "r": item.word("R"),
            "line": getattr(item, "number", index + 1),
        }

    # Plain mapping (dict) — same shape model_from_moves accepts.
    if isinstance(item, Mapping):
        cmd = item.get("type", "G1")
        return {
            "cmd": cmd,
            "x": item.get("x"), "y": item.get("y"), "z": item.get("z"),
            "f": item.get("f", item.get("feed")), "e": item.get("e"),
            "i": item.get("i"), "j": item.get("j"), "r": item.get("r"),
            "line": item.get("line", index + 1),
        }
    return None


def _comment_text(line: str) -> str:
    """The comment portion of a G-code line: after ``;`` and inside ``(...)``."""
    text = ""
    if ";" in line:
        text += " " + line.split(";", 1)[1]
    open_paren = line.find("(")
    if open_paren != -1:
        close = line.find(")", open_paren + 1)
        text += " " + (line[open_paren + 1:close] if close != -1 else line[open_paren + 1:])
    return text


def infer_burn_mode_from_text(gcode: str) -> bool:
    """Best-effort guess: is this raw G-code a laser/beam ('burn') job?

    Raw text carries no machine profile, so intent can only be read from the
    program itself. This looks for ``laser`` / ``beam`` / ``burn`` in **comments**
    — a distinctive, low-false-positive signal. A bare ``M3``/``M4`` + ``S`` is
    deliberately NOT treated as laser: that is exactly how a CNC spindle starts,
    so keying off it would misclassify ordinary router programs. Conservative by
    design — when unsure it returns ``False`` (cut). It never infers machine
    readiness, only cut-vs-burn intent for preview classification.
    """
    for raw_line in gcode.splitlines():
        comment = _comment_text(raw_line).lower()
        if comment and any(marker in comment for marker in _BURN_TEXT_MARKERS):
            return True
    return False


def _moves_and_laser(parsed_program: Any) -> tuple:
    """Return (iterable_of_moves, laser_flag) for the many accepted input forms."""
    # Raw text -> parse into a typed program. Raw text has no machine profile, so
    # fall back to a comment-based burn-intent heuristic when the (default)
    # machine does not already declare a laser.
    if isinstance(parsed_program, str):
        from ..gcode.parser import parse_program_model
        prog = parse_program_model(parsed_program)
        is_laser = (prog.header.machine in _LASER_MACHINES
                    or infer_burn_mode_from_text(parsed_program))
        return prog.moves, is_laser

    # A typed GCodeProgram (duck-typed: has .moves and a .header.machine).
    moves = getattr(parsed_program, "moves", None)
    if moves is not None:
        header = getattr(parsed_program, "header", None)
        machine = getattr(header, "machine", None)
        return moves, machine in _LASER_MACHINES

    # Already a sequence of moves / ParsedLine / dicts.
    return parsed_program, False


def build_toolpath_model(parsed_program: Any, *, laser: Optional[bool] = None) -> List[ToolpathSegment]:
    """Build canonical :class:`ToolpathSegment`s from parsed G-code.

    ``parsed_program`` may be raw G-code text, a :class:`GCodeProgram`, or a
    sequence of moves / ParsedLine / move-dicts. Motion is classified into
    travel / cut / extrude / arc / burn, and each segment carries its distance,
    end Z, source line, and originating command.

    Pass ``laser=True`` to force burn classification when the input form does not
    carry machine context (a bare move list). This never renders.
    """
    moves, inferred_laser = _moves_and_laser(parsed_program)
    is_laser = inferred_laser if laser is None else laser

    segs: List[ToolpathSegment] = []
    cur = Point(0.0, 0.0, 0.0)
    feed: Optional[float] = None

    for idx, item in enumerate(moves):
        m = _normalize_move(item, idx)
        if m is None:
            continue
        cmd = m["cmd"]
        tx = _num(m["x"], cur.x)
        ty = _num(m["y"], cur.y)
        tz = _num(m["z"], cur.z)
        f = parse_number_or_none(m["f"])
        if f is not None:
            feed = f
        end = Point(tx, ty, tz)
        line = m["line"]

        if cmd in ("G2", "G3"):
            i = parse_number_or_none(m["i"])
            j = parse_number_or_none(m["j"])
            r = parse_number_or_none(m["r"])
            dist = _arc_distance(cur, end, i, j, r, clockwise=cmd == "G2")
            segs.append(ToolpathSegment(
                ARC, cur, end, feed, tz, line, cmd, dist))
            cur = end
            continue

        if cmd == "G0":
            seg_type = TRAVEL
            seg_feed: Optional[float] = None
        elif parse_number_or_none(m["e"]) is not None:
            seg_type = EXTRUDE
            seg_feed = feed
        else:
            seg_type = BURN if is_laser else CUT
            seg_feed = feed

        dist = geom.distance(geom.Point(cur.x, cur.y, cur.z),
                             geom.Point(end.x, end.y, end.z))
        segs.append(ToolpathSegment(seg_type, cur, end, seg_feed, tz, line, cmd, dist))
        cur = end

    return segs


def _arc_distance(start: Point, end: Point, i, j, r, clockwise: bool) -> float:
    """Arc length for a G2/G3 move.

    Uses the ``I/J`` center when present, else the signed ``R`` radius, else the
    chord length as a last resort. The swept angle must respect the arc
    direction: taking the raw ``atan2`` difference (or always folding it
    positive) silently returns the counter-clockwise sweep for every arc, which
    is wrong for clockwise arcs and for any sweep that is not the shorter of the
    two. ``geom.arc_length`` takes the magnitude, so a negative (clockwise)
    sweep still yields a non-negative length.

    For ``R``-mode arcs the direction does not change the length; the G-code
    convention that a **negative** ``R`` selects the major (>180 degree) arc
    does. The center is not reconstructed — the chord and radius fully determine
    the swept angle.

    Malformed-geometry policy: preview length is best-effort. An ``R`` arc can
    only span a chord up to ``2*R``; if the endpoints are farther apart than
    that (inconsistent program, not mere float drift) no real arc exists, so
    this returns the straight-line chord rather than fabricating a semicircle.
    A chord that merely touches or drifts just past ``2*R`` is treated as a
    genuine semicircle.
    """
    if i is not None and j is not None:
        cx, cy = start.x + i, start.y + j
        radius = math.hypot(start.x - cx, start.y - cy)
        a0 = math.atan2(start.y - cy, start.x - cx)
        a1 = math.atan2(end.y - cy, end.x - cx)
        return geom.arc_length(radius, _signed_sweep(a0, a1, clockwise))
    if r is not None and r != 0:
        radius = abs(r)
        chord = geom.distance_2d(geom.Point(start.x, start.y, start.z),
                                 geom.Point(end.x, end.y, end.z))
        ratio = chord / (2 * radius)
        if ratio <= 1.0 + _ARC_CHORD_TOL:
            # chord = 2 R sin(sweep/2); minor arc has sweep in [0, pi]. The
            # min() absorbs drift so an exact semicircle stays a semicircle.
            minor = 2 * math.asin(min(1.0, ratio))
            sweep = (2 * math.pi - minor) if r < 0 else minor
            return geom.arc_length(radius, sweep)
        # Impossible geometry (chord > 2R): fall through to the chord length.
    return geom.distance(geom.Point(start.x, start.y, start.z),
                         geom.Point(end.x, end.y, end.z))
