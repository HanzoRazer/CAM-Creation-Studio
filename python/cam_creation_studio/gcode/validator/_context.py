"""Shared analysis context for the validator rule modules.

Parsing and the handful of program-wide facts (is this a printer? a laser? are
units declared?) are computed once and handed to each rule module, so the rules
themselves stay small and declarative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..parser import ParsedLine, parse_program


def _is_printer(lines: List[ParsedLine]) -> bool:
    for ln in lines:
        if ln.has("E"):
            return True
        for code in (104, 109, 140, 190):
            if ln.mword(code):
                return True
    return False


@dataclass(frozen=True)
class ProgramContext:
    """Precomputed facts about a program that rules reason over."""

    lines: List[ParsedLine]
    machine: Optional[str]
    printer: bool
    laser: bool
    cnc_like: bool

    @property
    def motion_lines(self) -> List[ParsedLine]:
        return [ln for ln in self.lines if ln.motion is not None]

    @property
    def units_declared(self) -> bool:
        return any(ln.gword(20) or ln.gword(21) for ln in self.lines)

    @property
    def has_safe_z(self) -> bool:
        return any(ln.motion == "G0" and ln.has("Z") for ln in self.lines)

    @property
    def has_end(self) -> bool:
        return any(ln.mword(2) or ln.mword(30) for ln in self.lines)


def build_context(text: str, machine: Optional[str]) -> ProgramContext:
    lines = parse_program(text)
    printer = _is_printer(lines)
    laser = machine in ("laser", "laserGrbl")
    cnc_like = machine in ("cnc", "genericCnc") or (
        machine is None and not printer and not laser
    )
    return ProgramContext(
        lines=lines, machine=machine, printer=printer, laser=laser, cnc_like=cnc_like
    )
