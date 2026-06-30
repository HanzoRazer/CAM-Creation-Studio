"""Centralized safety messaging.

One place for the standing safety reminders so the rest of the app (and any UI)
shows consistent, advisory-only language. These are reminders, not guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

DISCLAIMER = (
    "CAM-Creation-Studio is an educational tool. It does not certify machine "
    "readiness, replace professional CAM validation, or guarantee safe machine "
    "execution. Generated G-code is a starting point; the preview is not a "
    "simulation. Always verify and air-cut before running."
)


@dataclass(frozen=True)
class SafetyRule:
    id: str
    message: str


_RULES: List[SafetyRule] = [
    SafetyRule("PREVIEW_NOT_SIMULATION", "Preview is a model, not a simulation."),
    SafetyRule("VERIFY_GCODE", "Generated G-code must be verified before running."),
    SafetyRule("FEEDS_ADVISORY", "Feeds and speeds are advisory starting points."),
    SafetyRule("AIR_CUT", "Air-cut above the stock first to catch crashes."),
    SafetyRule("CONFIRM_WCS", "Confirm the work coordinate system / part zero."),
    SafetyRule("CONFIRM_UNITS", "Confirm units (mm vs inch) before running."),
    SafetyRule("CONFIRM_MODE", "Confirm spindle / laser mode and power."),
    SafetyRule("CONFIRM_CLEARANCE", "Confirm tool clearance and safe-Z heights."),
]

_BY_ID = {r.id: r for r in _RULES}


def all_rules() -> List[SafetyRule]:
    """Every standing safety rule."""
    return list(_RULES)


def get_rule(rule_id: str) -> SafetyRule:
    if rule_id not in _BY_ID:
        raise ValueError(f"Unknown safety rule: {rule_id}")
    return _BY_ID[rule_id]


def checklist(machine: Optional[str] = None) -> List[str]:
    """A pre-run checklist as plain strings, optionally tailored to a machine."""
    items = [r.message for r in _RULES]
    if machine in ("laser", "laserGrbl"):
        items.append("Laser: confirm eye protection and enclosure/ventilation.")
    elif machine in ("cnc", "genericCnc"):
        items.append("CNC: confirm workholding and that the spindle is started (M3).")
    elif machine == "marlin":
        items.append("Marlin: confirm hotend/bed target temps before extruding.")
    return items
