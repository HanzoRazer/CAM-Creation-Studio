"""Enumerations for the CAM-Creation-Studio core.

One home for the small closed sets of choices the domain model reasons about, so
there are no bare strings scattered through the code. Every enum is ``str``-based
so its members compare equal to, and serialize as, their wire string. That keeps
existing string comparisons (``severity == "danger"``) and JSON round-trips
working while still giving callers real symbols to branch on.
"""

from __future__ import annotations

from enum import Enum


class Units(str, Enum):
    """Length units a program can declare."""

    MM = "mm"
    INCH = "in"

    @property
    def gcode_word(self) -> str:
        """The G-code word that declares these units: G21 (mm) or G20 (inch)."""
        return "G20" if self is Units.INCH else "G21"


class MoveType(str, Enum):
    """The motion commands the core understands."""

    RAPID = "G0"       # positioning rapid, non-cutting
    LINEAR = "G1"      # straight-line feed move
    ARC_CW = "G2"      # clockwise arc
    ARC_CCW = "G3"     # counter-clockwise arc

    @property
    def is_arc(self) -> bool:
        return self in (MoveType.ARC_CW, MoveType.ARC_CCW)

    @property
    def is_cut(self) -> bool:
        """True for feed/cut moves (everything except a rapid)."""
        return self is not MoveType.RAPID


class CutMode(str, Enum):
    """How an image-etch program removes/marks material.

    ``POWER``: toggle beam/spindle power per segment (laser-style).
    ``DEPTH``: plunge to an engrave depth, cut, retract (router-style).
    """

    POWER = "power"
    DEPTH = "depth"


class MachineType(str, Enum):
    """Broad machine families the dialect system targets."""

    MARLIN = "marlin"        # FDM 3D printer, extrusion on E
    CNC = "genericCnc"       # spindle-driven mill/router
    LASER = "laserGrbl"      # diode/CO2 engraver, power via S


class DiagnosticSeverity(str, Enum):
    """Advisory severity for a :class:`~cam_creation_studio.models.Diagnostic`."""

    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"
