"""Starter tool presets.

Diameters are in millimetres (imperial sizes converted). Flute counts and notes
are typical starting points, not specifications for any particular cutter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..shared.units import in_to_mm


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    diameter_mm: float
    flutes: Optional[int]
    kind: str  # 'endmill' | 'vbit' | 'ballnose' | 'engraver' | 'laser' | 'knife'
    notes: str = ""


_TOOLS: List[Tool] = [
    Tool("endmill_1_8", '1/8" end mill', in_to_mm(0.125), 2, "endmill", "3.175 mm; common hobby size."),
    Tool("endmill_1_4", '1/4" end mill', in_to_mm(0.25), 2, "endmill", "6.35 mm; rigid general-purpose."),
    Tool("vbit", "V-bit", in_to_mm(0.25), 1, "vbit", "Engraving/chamfer; effective width varies with depth."),
    Tool("ballnose", "Ball nose", in_to_mm(0.25), 2, "ballnose", "3D contouring; scallop depends on stepover."),
    Tool("engraver", "Engraving bit", in_to_mm(0.125), 1, "engraver", "Fine detail; shallow passes."),
    Tool("laser_diode", "Laser diode", 0.1, None, "laser", "No flutes; 'feed' is travel speed, power via S."),
    Tool("drag_knife", "Drag knife (placeholder)", 0.0, None, "knife", "Placeholder; vinyl/card cutting, no spindle."),
]

_BY_ID: Dict[str, Tool] = {t.id: t for t in _TOOLS}


def get_tool(tool_id: str) -> Tool:
    if tool_id not in _BY_ID:
        raise ValueError(f"Unknown tool: {tool_id}")
    return _BY_ID[tool_id]


def list_tools() -> List[Tool]:
    return list(_TOOLS)
