"""Starter material presets with CONSERVATIVE chipload ranges.

These are advisory ranges for learning, not hard claims. Chiploads are given in
millimetres per tooth and depend heavily on tool, machine rigidity, and finish.
Always verify against your tooling manufacturer's data and your own test cuts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Material:
    id: str
    label: str
    # Conservative chipload range (mm/tooth), as (low, high).
    chipload_mm: Tuple[float, float]
    notes: str = ""

    @property
    def chipload_mid(self) -> float:
        low, high = self.chipload_mm
        return (low + high) / 2


_MATERIALS: List[Material] = [
    Material("softwood", "Softwood", (0.05, 0.13), "Pine/cedar; forgiving, watch for tear-out."),
    Material("hardwood", "Hardwood", (0.04, 0.10), "Oak/maple; denser, lower chipload than softwood."),
    Material("plywood", "Plywood", (0.04, 0.10), "Glue layers dull tools; moderate feeds."),
    Material("mdf", "MDF", (0.05, 0.13), "Abrasive dust; use dust collection, sharp tooling."),
    Material("acrylic", "Acrylic", (0.05, 0.13), "Melts if too slow; keep the chip moving, single flute helps."),
    Material("aluminum", "Aluminum", (0.025, 0.08), "Needs lube/air; risk of welding chips, go shallow."),
    Material("brass", "Brass", (0.02, 0.06), "Free-cutting but grabby; light passes."),
    Material("plastic", "Plastic (general)", (0.05, 0.13), "Varies widely by polymer; test first."),
]

_BY_ID: Dict[str, Material] = {m.id: m for m in _MATERIALS}


def get_material(material_id: str) -> Material:
    if material_id not in _BY_ID:
        raise ValueError(f"Unknown material: {material_id}")
    return _BY_ID[material_id]


def list_materials() -> List[Material]:
    return list(_MATERIALS)
