"""Feeds/speeds -> Creator handoff contract.

Mirrors the browser prototype's localStorage ``gcodeHandoff`` behavior, but as a
storage-agnostic, pure core. A handoff is an *advisory* payload:

    {"rpm": 18000, "feed": 1200, "units": "mm", "material": "MDF"}

It is a "suggested starting point that requires operator verification" — never a
hard claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

HANDOFF_KEY = "gcodeHandoff"


@dataclass(frozen=True)
class Handoff:
    rpm: float
    feed: float
    units: str = "mm"
    material: Optional[str] = None

    @staticmethod
    def from_mapping(data: Mapping[str, Any]) -> Optional["Handoff"]:
        """Build a Handoff from a mapping, or None if it lacks a valid rpm."""
        if not data or not data.get("rpm"):
            return None
        return Handoff(
            rpm=data["rpm"],
            feed=data.get("feed", 0),
            units=data.get("units", "mm"),
            material=data.get("material"),
        )


def parse_handoff(raw: Optional[str]) -> Optional[Handoff]:
    """Parse a JSON handoff string. Returns None on absent/invalid input."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, Mapping):
        return None
    return Handoff.from_mapping(data)


def handoff_text(handoff: Optional[Handoff]) -> str:
    """Human-readable banner summary, e.g. 'S18000 RPM | F1200 mm/min | MDF'."""
    if handoff is None:
        return ""
    rate = "mm/min" if handoff.units == "mm" else "in/min"
    text = f"S{handoff.rpm} RPM | F{handoff.feed} {rate}"
    if handoff.material:
        text += f" | {handoff.material}"
    return text


def _is_cut_move(move_type: str) -> bool:
    return move_type in ("G1", "G2", "G3")


def apply_handoff_to_config(config: Mapping[str, Any], handoff: Handoff) -> dict:
    """Compute the config patch produced by applying a handoff (pure).

    Effects (mirror the original Creator):
      - switch to CNC mode
      - set spindle RPM and etch feed from the handoff
      - set units from the handoff
      - fill the feed on any cut move missing/non-positive
    """
    moves = []
    for m in config.get("moves", []):
        m = dict(m)
        f = m.get("f", "")
        missing = f in ("", None) or _to_float(f) <= 0
        if _is_cut_move(m.get("type", "")) and missing:
            m["f"] = str(handoff.feed)
        moves.append(m)
    return {
        "machine": "genericCnc",
        "spindleRpm": str(handoff.rpm),
        "etchFeed": str(handoff.feed),
        "units": "mm" if handoff.units == "mm" else "in",
        "moves": moves,
    }


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
