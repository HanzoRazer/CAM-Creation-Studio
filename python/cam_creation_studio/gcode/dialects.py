"""Starter dialect profiles.

EDUCATIONAL "starter dialect profiles", not certified post-processors. Each
describes how a machine family tends to open and close a program and which axes
it expects. No guarantee the output is safe to run on any specific machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Mapping

from ..shared.numbers import is_positive_number


@dataclass(frozen=True)
class LineSpec:
    """A renderable line descriptor: command word + parameter words + comment."""

    cmd: str
    words: Mapping[str, Any] = field(default_factory=dict)
    comment: str = ""


@dataclass(frozen=True)
class Dialect:
    id: str
    label: str
    allowed_axes: tuple
    default_units: str
    supports_arcs: bool
    startup_comment: str
    header_extras: Callable[[Mapping[str, Any]], List[LineSpec]]
    footer_extras: Callable[[Mapping[str, Any]], List[LineSpec]]


def _marlin_header(cfg: Mapping[str, Any]) -> List[LineSpec]:
    lines: List[LineSpec] = []
    bed = cfg.get("bed") if is_positive_number(cfg.get("bed")) else None
    hotend = cfg.get("hotend") if is_positive_number(cfg.get("hotend")) else None
    if bed is not None:
        lines.append(LineSpec("M140", {"S": bed}, "set bed temp"))
    if hotend is not None:
        lines.append(LineSpec("M104", {"S": hotend}, "set hotend temp"))
    if bed is not None:
        lines.append(LineSpec("M190", {"S": bed}, "wait for bed"))
    if hotend is not None:
        lines.append(LineSpec("M109", {"S": hotend}, "wait for hotend"))
    return lines


def _marlin_footer(cfg: Mapping[str, Any]) -> List[LineSpec]:
    lines = [LineSpec("M104", {"S": 0}, "hotend off")]
    if is_positive_number(cfg.get("bed")):
        lines.append(LineSpec("M140", {"S": 0}, "bed off"))
    lines.append(LineSpec("M84", {}, "disable steppers"))
    return lines


def _cnc_header(cfg: Mapping[str, Any]) -> List[LineSpec]:
    if not cfg.get("spindleOn"):
        return []
    return [LineSpec("M3", {"S": cfg.get("spindleRpm", 0)}, "spindle on")]


def _cnc_footer(cfg: Mapping[str, Any]) -> List[LineSpec]:
    return [LineSpec("M5", {}, "spindle off")] if cfg.get("spindleOn") else []


def _laser_header(cfg: Mapping[str, Any]) -> List[LineSpec]:
    return [LineSpec("M5", {}, "beam off")]


def _laser_footer(cfg: Mapping[str, Any]) -> List[LineSpec]:
    return [LineSpec("M5", {}, "beam off")]


marlin = Dialect(
    id="marlin",
    label="Marlin · 3D Printer",
    allowed_axes=("X", "Y", "Z", "E", "F"),
    default_units="mm",
    supports_arcs=False,
    startup_comment="heat up, home, move to safe Z",
    header_extras=_marlin_header,
    footer_extras=_marlin_footer,
)

generic_cnc = Dialect(
    id="genericCnc",
    label="CNC Mill",
    allowed_axes=("X", "Y", "Z", "I", "J", "F"),
    default_units="mm",
    supports_arcs=True,
    startup_comment="home, start spindle, move to safe Z",
    header_extras=_cnc_header,
    footer_extras=_cnc_footer,
)

laser_grbl = Dialect(
    id="laserGrbl",
    label="Laser · GRBL",
    allowed_axes=("X", "Y", "F"),
    default_units="mm",
    supports_arcs=True,
    startup_comment="home, beam off, move to safe Z",
    header_extras=_laser_header,
    footer_extras=_laser_footer,
)

_REGISTRY = {d.id: d for d in (marlin, generic_cnc, laser_grbl)}
_ALIASES = {"cnc": "genericCnc", "laser": "laserGrbl"}


def get_dialect(dialect_id: str) -> Dialect:
    """Look up a dialect by id (or known alias). Raises on unknown ids."""
    key = dialect_id if dialect_id in _REGISTRY else _ALIASES.get(dialect_id)
    dialect = _REGISTRY.get(key)
    if dialect is None:
        raise ValueError(f"Unknown dialect: {dialect_id}")
    return dialect


def list_dialects() -> List[Dialect]:
    return list(_REGISTRY.values())
