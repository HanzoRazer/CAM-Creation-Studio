"""Starter machine profiles.

These are starter profiles for learning and rough bounds-checking — NOT certified
machine definitions and NOT post-processor configurations. Only fields we are
confident about are populated; we do not assert controller dialect, acceleration,
or post behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class MachineProfile:
    id: str
    label: str
    # Work envelope in mm (x, y, z); None if unspecified.
    work_area_mm: Optional[Tuple[float, float, float]] = None
    max_rpm: Optional[float] = None
    suggested_dialect: Optional[str] = None
    # Additional CONFIRMED specs only (free-form, advisory).
    specs: Dict[str, str] = field(default_factory=dict)
    notes: str = ""


# Deprecated alias: the profile was named ``Machine`` before CS-002.
Machine = MachineProfile


_MACHINES: List[MachineProfile] = [
    MachineProfile(
        id="genericCncRouter",
        label="Generic CNC router",
        work_area_mm=(300.0, 300.0, 80.0),
        max_rpm=18000.0,
        suggested_dialect="genericCnc",
        notes="Generic hobby/benchtop router envelope; adjust to your machine.",
    ),
    MachineProfile(
        id="desktop3018",
        label="Desktop 3018 CNC",
        work_area_mm=(300.0, 180.0, 45.0),
        max_rpm=10000.0,
        suggested_dialect="genericCnc",
        notes="Small desktop engraver; light cuts only.",
    ),
    MachineProfile(
        id="bcam2030ca_placeholder",
        label="BCAMCNC 2030CA (placeholder)",
        work_area_mm=(2000.0, 3000.0, 200.0),
        max_rpm=24000.0,
        suggested_dialect=None,  # controller dialect NOT asserted
        specs={
            "spindle": "9.0 kW",
            "tool_holder": "ISO30",
            "vacuum_pumps": "2 x 5.5 kW",
        },
        notes=(
            "Placeholder using only confirmed fields. Controller dialect, "
            "acceleration, and post behavior are NOT asserted here."
        ),
    ),
    MachineProfile(
        id="genericLaser",
        label="Generic laser engraver",
        work_area_mm=(400.0, 400.0, 0.0),
        max_rpm=None,
        suggested_dialect="laserGrbl",
        notes="Diode/CO2 engraver; 'feed' is travel speed, power via S.",
    ),
    MachineProfile(
        id="marlinPrinter",
        label="Marlin 3D printer",
        work_area_mm=(220.0, 220.0, 250.0),
        max_rpm=None,
        suggested_dialect="marlin",
        notes="FDM printer envelope; extrusion on the E axis.",
    ),
]

_BY_ID: Dict[str, MachineProfile] = {m.id: m for m in _MACHINES}


def get_machine(machine_id: str) -> MachineProfile:
    if machine_id not in _BY_ID:
        raise ValueError(f"Unknown machine: {machine_id}")
    return _BY_ID[machine_id]


def list_machines() -> List[MachineProfile]:
    return list(_MACHINES)
