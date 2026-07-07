"""Safety validation rules — could this program do something dangerous?

  CUT_WITHOUT_FEED              a cutting move with no feed rate in effect
  ARC_WITHOUT_CENTER_OR_RADIUS  G2/G3 lacking I/J or R
  EXTRUSION_WITHOUT_HOTEND      E extrusion with no hotend heat set
  NEGATIVE_Z_IN_LASER_MODE      negative Z while in laser/power mode
  SPINDLE_OFF_WITH_CUTS         CNC cutting moves but the spindle never starts

These are advisory hints for a beginner, never a safety guarantee.
"""

from __future__ import annotations

from typing import List

from ...enums import DiagnosticSeverity
from ...models import Diagnostic
from ._context import ProgramContext


def check(ctx: ProgramContext) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []

    feed_set = False
    hotend_set = False
    spindle_ever_on = False
    has_cut_moves = False
    extrusion_flagged = False

    for ln in ctx.lines:
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
                diagnostics.append(Diagnostic(
                    DiagnosticSeverity.WARNING, "CUT_WITHOUT_FEED",
                    "Cutting move with no feed rate (F) in effect.", ln.number))
            if ln.is_arc and not (ln.has("I") or ln.has("J") or ln.has("R")):
                diagnostics.append(Diagnostic(
                    DiagnosticSeverity.WARNING, "ARC_WITHOUT_CENTER_OR_RADIUS",
                    "Arc move (G2/G3) is missing I/J center or R radius.", ln.number))

        if ln.has("E") and not hotend_set and not extrusion_flagged:
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.DANGER, "EXTRUSION_WITHOUT_HOTEND",
                "Extrusion (E) with no hotend temperature set.", ln.number))
            extrusion_flagged = True

        if ctx.laser and ln.has("Z") and (ln.word("Z") or 0) < 0:
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.DANGER, "NEGATIVE_Z_IN_LASER_MODE",
                "Negative Z while in laser/power mode.", ln.number))

    if ctx.cnc_like and has_cut_moves and not spindle_ever_on:
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.DANGER, "SPINDLE_OFF_WITH_CUTS",
            "Cutting moves present but the spindle (M3/M4) never starts."))

    return diagnostics
