"""The CAM-Creation-Studio domain model.

This module is the vocabulary every other layer speaks. Instead of passing raw
dictionaries around, the core builds and reasons about immutable dataclasses:

    GCodeProgram
        header:  ProgramHeader
        moves:   [Move | ArcMove, ...]
        footer:  ProgramFooter

    Move / ArcMove   — a single motion instruction (a program's body)
    Diagnostic       — one advisory validation finding
    Point / Bounds   — geometry primitives (re-exported from shared.geometry)

Profile objects (:class:`MachineProfile`, :class:`Material`, :class:`Tool`) and
the feeds result (:class:`FeedRecommendation`) live with their libraries and are
re-exported here so ``cam_creation_studio.models`` is the one import a consumer
needs for "the shape of the domain".

Everything here is machine-independent: nothing in this module knows about GRBL,
Mach4, LinuxCNC, or Marlin. Only the dialect adapters know those differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from .enums import DiagnosticSeverity, MoveType, Units
from .shared.geometry import Bounds, Point, bounds as _bounds_of

# Re-exports so `from cam_creation_studio.models import ...` is a one-stop shop.
from .feeds_speeds.machines import MachineProfile  # noqa: F401
from .feeds_speeds.materials import Material  # noqa: F401
from .feeds_speeds.tools import Tool  # noqa: F401
from .feeds_speeds.calculator import FeedRecommendation  # noqa: F401

__all__ = [
    "Point",
    "Bounds",
    "Move",
    "ArcMove",
    "Diagnostic",
    "ProgramHeader",
    "ProgramFooter",
    "GCodeProgram",
    "MachineProfile",
    "Material",
    "Tool",
    "FeedRecommendation",
    "move_from_dict",
]


# --------------------------------------------------------------------------- #
# Motion
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Move:
    """A single linear or rapid motion instruction (G0/G1).

    Any coordinate left ``None`` is simply omitted from the emitted line, which
    preserves G-code's modal behavior (unset axes hold their prior value).
    ``e`` is extrusion (Marlin only); ``feed`` is the F word.
    """

    type: MoveType = MoveType.LINEAR
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    feed: Optional[float] = None
    e: Optional[float] = None
    comment: str = ""

    @property
    def is_arc(self) -> bool:
        return False

    @property
    def endpoint(self) -> Point:
        """The target point (unset axes default to 0.0 for geometry purposes)."""
        return Point(self.x or 0.0, self.y or 0.0, self.z or 0.0)


@dataclass(frozen=True, slots=True)
class ArcMove:
    """A circular-arc motion instruction (G2 clockwise / G3 counter-clockwise).

    The arc center is given by the I/J offsets from the arc's start point, or by
    a radius ``r`` (R-word form). At least one of (i, j) or r should be present
    for the arc to be well defined.
    """

    type: MoveType = MoveType.ARC_CW
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    i: Optional[float] = None
    j: Optional[float] = None
    r: Optional[float] = None
    feed: Optional[float] = None
    comment: str = ""

    def __post_init__(self) -> None:
        if self.type not in (MoveType.ARC_CW, MoveType.ARC_CCW):
            raise ValueError("ArcMove.type must be ARC_CW (G2) or ARC_CCW (G3)")

    @property
    def is_arc(self) -> bool:
        return True

    @property
    def clockwise(self) -> bool:
        return self.type is MoveType.ARC_CW

    @property
    def endpoint(self) -> Point:
        return Point(self.x or 0.0, self.y or 0.0, self.z or 0.0)


AnyMove = Union[Move, ArcMove]


def move_from_dict(data: dict) -> AnyMove:
    """Build a :class:`Move` or :class:`ArcMove` from a plain dict.

    Chooses ``ArcMove`` when the data describes an arc (type G2/G3 or the
    presence of I/J/R), else ``Move``. Numeric fields are coerced from strings.
    """
    def num(key):
        v = data.get(key)
        if v in (None, ""):
            return None
        return float(v)

    raw_type = data.get("type", "G1")
    mtype = MoveType(raw_type) if not isinstance(raw_type, MoveType) else raw_type
    is_arc = mtype.is_arc or any(k in data and data[k] not in (None, "") for k in ("i", "j", "r"))

    if is_arc:
        if not mtype.is_arc:
            mtype = MoveType.ARC_CW
        return ArcMove(
            type=mtype, x=num("x"), y=num("y"), z=num("z"),
            i=num("i"), j=num("j"), r=num("r"), feed=num("f") if "f" in data else num("feed"),
            comment=data.get("comment", ""),
        )
    return Move(
        type=mtype, x=num("x"), y=num("y"), z=num("z"),
        feed=num("f") if "f" in data else num("feed"),
        e=num("e"), comment=data.get("comment", ""),
    )


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One advisory validation finding. Never blocks generation."""

    severity: DiagnosticSeverity
    code: str
    message: str
    line: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.severity, DiagnosticSeverity):
            object.__setattr__(self, "severity", DiagnosticSeverity(self.severity))

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "line": self.line,
        }


# --------------------------------------------------------------------------- #
# Program envelope
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ProgramHeader:
    """Typed description of a program's opening block.

    Captures the intent the generator turns into header lines: units, absolute
    vs. relative positioning, an optional home, the target machine dialect, the
    safe-Z retract height, and the dialect-specific startup values (spindle for
    CNC, hotend/bed for Marlin).
    """

    units: Units = Units.MM
    absolute: bool = True
    home: bool = False
    machine: str = "genericCnc"
    safe_z: float = 0.0
    spindle_on: bool = False
    spindle_rpm: Optional[float] = None
    hotend_c: Optional[float] = None
    bed_c: Optional[float] = None
    comment: str = ""


@dataclass(frozen=True, slots=True)
class ProgramFooter:
    """Typed description of a program's closing block."""

    units: Units = Units.MM
    machine: str = "genericCnc"
    safe_z: float = 0.0
    spindle_on: bool = False
    park: bool = True
    hotend_c: Optional[float] = None
    bed_c: Optional[float] = None
    end_code: str = "M30"
    comment: str = ""


@dataclass(frozen=True, slots=True)
class GCodeProgram:
    """A complete program: a header, an ordered body of moves, and a footer."""

    header: ProgramHeader = field(default_factory=ProgramHeader)
    moves: List[AnyMove] = field(default_factory=list)
    footer: ProgramFooter = field(default_factory=ProgramFooter)

    def bounds(self) -> Optional[Bounds]:
        """Axis-aligned bounds over the endpoints of all moves (or ``None``)."""
        pts = [m.endpoint for m in self.moves]
        return _bounds_of(pts)

    # GCodeProgram carries a Union[Move, ArcMove] list, which the generic
    # serializer can't disambiguate on the way back in — so it owns its own
    # round-trip using ``move_from_dict``.
    def to_dict(self) -> dict:
        from .shared.serialization import to_dict as _to_dict
        return {
            "header": _to_dict(self.header),
            "moves": [_to_dict(m) for m in self.moves],
            "footer": _to_dict(self.footer),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "GCodeProgram":
        from .shared.serialization import from_dict as _from_dict
        header = _from_dict(ProgramHeader, data.get("header", {}))
        footer = _from_dict(ProgramFooter, data.get("footer", {}))
        moves = [move_from_dict(m) for m in data.get("moves", [])]
        return cls(header=header, moves=moves, footer=footer)

    @classmethod
    def from_json(cls, text: str) -> "GCodeProgram":
        import json
        return cls.from_dict(json.loads(text))
