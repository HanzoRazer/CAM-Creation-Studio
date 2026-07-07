"""Cross-dialect contamination rules — is a command in the wrong machine family?

A program written for one machine family often carries commands that make no
sense (or are dangerous) on another. These rules flag that mismatch:

  EXTRUDER_WORD_IN_CNC     an E (extrusion) word on a CNC/router program
  HEATER_COMMAND_IN_CNC    a hotend/bed heater command (M104/M109/M140/M190) on CNC
  SPINDLE_COMMAND_IN_FDM   a spindle command (M3/M4) on an FDM printer program
  MARLIN_COMMAND_IN_GRBL   a Marlin-only command (heater or E) on a GRBL/laser dialect

Each is advisory — a hint that the target machine and the code disagree, never a
hard block.
"""

from __future__ import annotations

from typing import List

from ...enums import DiagnosticSeverity
from ...models import Diagnostic
from ._context import ProgramContext

_HEATER_CODES = (104, 109, 140, 190)
_GRBL_MACHINES = ("laser", "laserGrbl", "grbl")


def _has_heater(ln) -> bool:
    return any(ln.mword(code) for code in _HEATER_CODES)


def check(ctx: ProgramContext) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []

    for ln in ctx.lines:
        heater = _has_heater(ln)
        extrude = ln.has("E")
        spindle = ln.mword(3) or ln.mword(4)

        if ctx.cnc_like and extrude:
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.WARNING, "EXTRUDER_WORD_IN_CNC",
                "Extrusion word (E) on a CNC/router program — E has no meaning "
                "on a spindle machine.", ln.number))
        if ctx.cnc_like and heater:
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.WARNING, "HEATER_COMMAND_IN_CNC",
                "Heater command (M104/M109/M140/M190) on a CNC/router program.",
                ln.number))
        if ctx.printer and spindle:
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.WARNING, "SPINDLE_COMMAND_IN_FDM",
                "Spindle command (M3/M4) on an FDM printer program.", ln.number))
        if ctx.machine in _GRBL_MACHINES and (heater or extrude):
            diagnostics.append(Diagnostic(
                DiagnosticSeverity.WARNING, "MARLIN_COMMAND_IN_GRBL",
                "Marlin-only command (heater or E word) on a GRBL/laser dialect.",
                ln.number))

    return diagnostics
