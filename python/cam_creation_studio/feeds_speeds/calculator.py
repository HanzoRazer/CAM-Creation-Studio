"""Advisory feeds/speeds calculator.

Everything this produces is a *suggested starting point that requires operator
verification* — never a hard claim. Units are kept explicit (mm).

Formulas:
    feed_rate     = rpm * flutes * chipload         (mm/min)
    surface_speed = pi * tool_diameter * rpm        (mm/min)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from ..shared.numbers import round_for_gcode
from .materials import Material, get_material

ADVISORY = "Suggested starting point - requires operator verification."


@dataclass(frozen=True)
class FeedsResult:
    rpm: float
    feed_rate: float  # mm/min
    chipload: float  # mm/tooth
    surface_speed: float  # mm/min
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def surface_speed_m_min(self) -> float:
        return round_for_gcode(self.surface_speed / 1000.0, 3)

    def as_dict(self) -> dict:
        return {
            "rpm": self.rpm,
            "feed_rate": self.feed_rate,
            "chipload": self.chipload,
            "surface_speed": self.surface_speed,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


def calculate_feeds(
    *,
    tool_diameter_mm: float,
    flutes: int,
    spindle_rpm: float,
    chipload: Optional[float] = None,
    material: Optional[str] = None,
    feed_override: Optional[float] = None,
) -> FeedsResult:
    """Compute an advisory feed rate and surface speed.

    Provide ``chipload`` directly, or a ``material`` id to use that material's
    conservative mid-range chipload. ``feed_override`` (if given) replaces the
    computed feed but the computed value is still reported in notes.
    """
    notes: List[str] = [ADVISORY]
    warnings: List[str] = []

    mat: Optional[Material] = None
    if chipload is None:
        if material is None:
            raise ValueError("Provide either chipload or material.")
        mat = get_material(material)
        chipload = mat.chipload_mid
        notes.append(
            f"Chipload {chipload:g} mm/tooth from {mat.label} conservative range "
            f"{mat.chipload_mm[0]:g}-{mat.chipload_mm[1]:g}."
        )
    elif material is not None:
        mat = get_material(material)
        low, high = mat.chipload_mm
        if not (low <= chipload <= high):
            warnings.append(
                f"Chipload {chipload:g} is outside {mat.label} conservative range "
                f"{low:g}-{high:g} mm/tooth."
            )

    if flutes <= 0:
        raise ValueError("flutes must be a positive integer.")
    if spindle_rpm <= 0:
        raise ValueError("spindle_rpm must be positive.")
    if tool_diameter_mm <= 0:
        warnings.append("Tool diameter is zero/negative; surface speed is not meaningful.")

    computed_feed = spindle_rpm * flutes * chipload
    surface_speed = math.pi * tool_diameter_mm * spindle_rpm

    feed_rate = computed_feed
    if feed_override is not None:
        feed_rate = feed_override
        notes.append(f"Feed overridden to {feed_override:g} mm/min (computed {computed_feed:g}).")

    return FeedsResult(
        rpm=round_for_gcode(spindle_rpm, 3),
        feed_rate=round_for_gcode(feed_rate, 3),
        chipload=round_for_gcode(chipload, 4),
        surface_speed=round_for_gcode(surface_speed, 3),
        notes=notes,
        warnings=warnings,
    )
