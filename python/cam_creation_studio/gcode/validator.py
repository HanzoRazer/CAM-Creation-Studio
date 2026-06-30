"""Non-blocking G-code validation.

Emits advisory warnings about a program — it never blocks generation. Warnings
are hints to help a beginner catch common mistakes; they are not a safety
guarantee. Each warning is ``{severity, code, message, line}``.

Rules (initial set):
  MISSING_SAFE_Z                  no rapid to a safe Z retract
  CUT_WITHOUT_FEED                a cutting move with no feed rate in effect
  SPINDLE_OFF_WITH_CUTS           CNC cutting moves but the spindle never starts
  EXTRUSION_WITHOUT_HOTEND        E extrusion with no hotend heat set
  NEGATIVE_Z_IN_LASER_MODE        negative Z while in laser/power mode
  ARC_WITHOUT_CENTER_OR_RADIUS    G2/G3 lacking I/J or R
  UNITS_NOT_DECLARED              no G20/G21 anywhere
  NO_FOOTER_SHUTDOWN              no program end (M2/M30)
  EMPTY_PROGRAM_BODY              no motion lines at all
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .parser import ParsedLine, parse_program

INFO = "info"
WARNING = "warning"
DANGER = "danger"


@dataclass(frozen=True)
class Warning:
    severity: str
    code: str
    message: str
    line: Optional[int] = None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "line": self.line,
        }


def _is_printer(lines: List[ParsedLine]) -> bool:
    for ln in lines:
        if ln.has("E"):
            return True
        for code in (104, 109, 140, 190):
            if ln.mword(code):
                return True
    return False


def validate_program(text: str, machine: Optional[str] = None) -> List[Warning]:
    """Validate a G-code program string. Returns a list of Warning (advisory)."""
    lines = parse_program(text)
    warnings: List[Warning] = []

    units_declared = any(ln.gword(20) or ln.gword(21) for ln in lines)
    has_safe_z = any(ln.motion == "G0" and ln.has("Z") for ln in lines)
    has_end = any(ln.mword(2) or ln.mword(30) for ln in lines)
    motion_lines = [ln for ln in lines if ln.motion is not None]

    printer = _is_printer(lines)
    laser = machine in ("laser", "laserGrbl")

    if not units_declared:
        warnings.append(Warning(DANGER, "UNITS_NOT_DECLARED",
                                "No G20/G21 — units are not declared. Confirm mm vs inch before running."))

    if not motion_lines:
        warnings.append(Warning(WARNING, "EMPTY_PROGRAM_BODY",
                                "Program has no motion moves (G0/G1/G2/G3)."))

    if not has_safe_z and motion_lines:
        warnings.append(Warning(WARNING, "MISSING_SAFE_Z",
                                "No rapid to a safe Z height — add a 'G0 Z<safe>' retract."))

    if not has_end and motion_lines:
        warnings.append(Warning(INFO, "NO_FOOTER_SHUTDOWN",
                                "No program end (M2/M30) — add a footer to shut down cleanly."))

    # --- modal scan ---
    feed_set = False
    hotend_set = False
    spindle_ever_on = False
    has_cut_moves = False
    extrusion_flagged = False

    for ln in lines:
        if ln.has("F"):
            feed_set = True
        if ln.mword(3) or ln.mword(4):
            spindle_ever_on = True
        if (ln.mword(104) or ln.mword(109)) and (ln.word("S") or 0) > 0:
            hotend_set = True

        motion = ln.motion
        if motion in ("G1", "G2", "G3"):
            has_cut_moves = True
            if not feed_set and not ln.has("F"):
                warnings.append(Warning(WARNING, "CUT_WITHOUT_FEED",
                                        "Cutting move with no feed rate (F) in effect.", ln.number))
            if ln.is_arc and not (ln.has("I") or ln.has("J") or ln.has("R")):
                warnings.append(Warning(WARNING, "ARC_WITHOUT_CENTER_OR_RADIUS",
                                        "Arc move (G2/G3) is missing I/J center or R radius.", ln.number))

        if ln.has("E") and not hotend_set and not extrusion_flagged:
            warnings.append(Warning(DANGER, "EXTRUSION_WITHOUT_HOTEND",
                                    "Extrusion (E) with no hotend temperature set.", ln.number))
            extrusion_flagged = True

        if laser and ln.has("Z") and (ln.word("Z") or 0) < 0:
            warnings.append(Warning(DANGER, "NEGATIVE_Z_IN_LASER_MODE",
                                    "Negative Z while in laser/power mode.", ln.number))

    cnc_like = machine in ("cnc", "genericCnc") or (machine is None and not printer and not laser)
    if cnc_like and has_cut_moves and not spindle_ever_on:
        warnings.append(Warning(DANGER, "SPINDLE_OFF_WITH_CUTS",
                                "Cutting moves present but the spindle (M3/M4) never starts."))

    return warnings
