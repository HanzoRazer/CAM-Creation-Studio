"""Structural validation rules — is the program well-formed as a whole?

  UNITS_NOT_DECLARED   no G20/G21 anywhere
  DUPLICATE_UNITS      both G20 and G21 declared (conflicting units)
  EMPTY_PROGRAM_BODY   no motion lines at all (canonical: EMPTY_PROGRAM)
  MISSING_SAFE_Z       no rapid to a safe Z retract
  NO_FOOTER_SHUTDOWN   no program end (M2/M30)
  UNKNOWN_GCODE        a G-word outside the recognized vocabulary
"""

from __future__ import annotations

from typing import List

from ...enums import DiagnosticSeverity
from ...models import Diagnostic
from ._context import ProgramContext

# G-codes the core recognizes. Anything else earns an advisory UNKNOWN_GCODE so
# a beginner catches a typo (G1O for G10) without the parser rejecting the line.
_KNOWN_GCODES = {
    0, 1, 2, 3, 4,               # motion + dwell
    17, 18, 19,                  # plane select
    20, 21,                      # units
    28, 30,                      # homing / return
    40, 41, 42, 43, 49,          # cutter comp / tool-length
    53, 54, 55, 56, 57, 58, 59,  # machine + work offsets
    61, 64,                      # path-control mode
    90, 91, 92, 93, 94,          # positioning / feed mode
}


def check(ctx: ProgramContext) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    has_motion = bool(ctx.motion_lines)

    if not ctx.units_declared:
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.DANGER, "UNITS_NOT_DECLARED",
            "No G20/G21 — units are not declared. Confirm mm vs inch before running."))
    elif any(ln.gword(20) for ln in ctx.lines) and any(ln.gword(21) for ln in ctx.lines):
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.DANGER, "DUPLICATE_UNITS",
            "Conflicting unit declarations — both G20 (inch) and G21 (mm) appear."))

    if not has_motion:
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.WARNING, "EMPTY_PROGRAM_BODY",
            "Program has no motion moves (G0/G1/G2/G3)."))

    if not ctx.has_safe_z and has_motion:
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.WARNING, "MISSING_SAFE_Z",
            "No rapid to a safe Z height — add a 'G0 Z<safe>' retract."))

    if not ctx.has_end and has_motion:
        diagnostics.append(Diagnostic(
            DiagnosticSeverity.INFO, "NO_FOOTER_SHUTDOWN",
            "No program end (M2/M30) — add a footer to shut down cleanly."))

    for ln in ctx.lines:
        for ltr, val in ln.words:
            if ltr == "G" and int(val) not in _KNOWN_GCODES:
                diagnostics.append(Diagnostic(
                    DiagnosticSeverity.WARNING, "UNKNOWN_GCODE",
                    f"Unrecognized G-code G{int(val)}.", ln.number))

    return diagnostics
