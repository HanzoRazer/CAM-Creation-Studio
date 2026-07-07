"""Advisory feeds/speeds calculator.

Everything this produces is a *suggested starting point that requires operator
verification* — never a hard claim. Units are kept explicit (mm).

Formulas:
    feed_rate     = rpm * flutes * chipload          (mm/min)
    surface_speed = pi * tool_diameter * rpm          (mm/min)
    MRR           = woc * doc * feed_rate              (mm^3/min)
    chip-thinning = 1 / sqrt(1 - (1 - 2*woc/D)^2)      (radial, capped at 4)
    power_w       = (MRR / 60) * specific_energy       (W, advisory only)
    torque_nm     = power_w * 60 / (2*pi*rpm)          (Nm, advisory only)

Power/torque use a coarse specific-cutting-energy estimate and are advisory
sanity bounds, not a validated cutting-force model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from ..shared.numbers import round_for_gcode
from .materials import Material, get_material

ADVISORY = "Suggested starting point - requires operator verification."

# --- Feeds/speeds diagnostic codes (CS-003 contract) ----------------------- #
RPM_EXCEEDS_MACHINE_LIMIT = "RPM_EXCEEDS_MACHINE_LIMIT"
POWER_EXCEEDS_MACHINE_LIMIT = "POWER_EXCEEDS_MACHINE_LIMIT"
WOC_EXCEEDS_DIAMETER = "WOC_EXCEEDS_DIAMETER"
DOC_AGGRESSIVE = "DOC_AGGRESSIVE"
CHIPLOAD_HIGH = "CHIPLOAD_HIGH"
MISSING_DIAMETER_OR_SPEED = "MISSING_DIAMETER_OR_SPEED"
ADVISORY_ONLY = "ADVISORY_ONLY"

# Coarse specific cutting energy (J/mm^3) by material id, for advisory power.
# These are order-of-magnitude only; real values vary with tool and condition.
_SPECIFIC_ENERGY_J_MM3 = {
    "softwood": 0.10, "hardwood": 0.20, "plywood": 0.15, "mdf": 0.10,
    "acrylic": 0.30, "aluminum": 0.70, "brass": 1.50, "plastic": 0.30,
    "mild_steel": 2.50, "stainless": 3.00,
}
_DEFAULT_SPECIFIC_ENERGY_J_MM3 = 1.0
_HP_PER_KW = 1.0 / 0.7457


@dataclass(frozen=True)
class FeedDiagnostic:
    """One coded feeds/speeds finding (advisory)."""

    code: str
    severity: str  # 'info' | 'warning' | 'danger'
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class FeedRecommendation:
    rpm: float
    feed_rate: float  # mm/min
    chipload: float  # mm/tooth
    surface_speed: float  # mm/min
    # Radial chip-thinning factor (1.0 when WOC >= D/2 or no WOC given), capped
    # at 4. Multiply the base chipload by this to hold a target chip thickness.
    chip_thinning_factor: float = 1.0
    # Material removal rate (mm^3/min); None until WOC and DOC are provided.
    material_removal_rate: Optional[float] = None
    # Advisory spindle-power/torque estimates. None until WOC/DOC allow an MRR.
    spindle_power_kw: Optional[float] = None
    spindle_power_hp: Optional[float] = None
    torque_nm: Optional[float] = None
    # Back-compat: power in watts (== spindle_power_kw * 1000 when known).
    power_w: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    diagnostics: List[FeedDiagnostic] = field(default_factory=list)

    @property
    def surface_speed_m_min(self) -> float:
        return round_for_gcode(self.surface_speed / 1000.0, 3)

    def as_dict(self) -> dict:
        return {
            "rpm": self.rpm,
            "feed_rate": self.feed_rate,
            "chipload": self.chipload,
            "surface_speed": self.surface_speed,
            "chip_thinning_factor": self.chip_thinning_factor,
            "material_removal_rate": self.material_removal_rate,
            "spindle_power_kw": self.spindle_power_kw,
            "spindle_power_hp": self.spindle_power_hp,
            "torque_nm": self.torque_nm,
            "power_w": self.power_w,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
            "diagnostics": [d.as_dict() for d in self.diagnostics],
        }


# Deprecated alias: this result was named ``FeedsResult`` before CS-002.
FeedsResult = FeedRecommendation


def _chip_thinning_factor(diameter_mm: float, woc_mm: Optional[float]) -> float:
    """Radial chip-thinning factor; 1.0 unless WOC is below half the diameter."""
    if woc_mm is None or diameter_mm <= 0 or woc_mm <= 0:
        return 1.0
    if woc_mm >= diameter_mm / 2.0:
        return 1.0
    ratio = 1.0 - 2.0 * woc_mm / diameter_mm  # in (0, 1)
    factor = 1.0 / math.sqrt(1.0 - ratio * ratio)
    return min(factor, 4.0)


def calculate_feeds(
    *,
    tool_diameter_mm: float,
    flutes: int,
    spindle_rpm: float,
    chipload: Optional[float] = None,
    material: Optional[str] = None,
    feed_override: Optional[float] = None,
    max_rpm: Optional[float] = None,
    woc_mm: Optional[float] = None,
    doc_mm: Optional[float] = None,
    max_power_kw: Optional[float] = None,
    specific_energy_j_mm3: Optional[float] = None,
) -> FeedRecommendation:
    """Compute an advisory feed rate and surface speed.

    Provide ``chipload`` directly, or a ``material`` id to use that material's
    conservative mid-range chipload. ``feed_override`` (if given) replaces the
    computed feed but the computed value is still reported in notes. ``max_rpm``
    (e.g. a machine profile's ceiling) adds a warning when ``spindle_rpm``
    exceeds it.

    When ``woc_mm`` and ``doc_mm`` are supplied, the result also carries a
    material-removal rate and advisory spindle-power/torque estimates, and the
    engagement diagnostics (WOC/DOC/power) become meaningful.
    """
    notes: List[str] = [ADVISORY]
    warnings: List[str] = []
    diagnostics: List[FeedDiagnostic] = [
        FeedDiagnostic(ADVISORY_ONLY, "info", ADVISORY),
    ]

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
        if chipload > high:
            diagnostics.append(FeedDiagnostic(
                CHIPLOAD_HIGH, "warning",
                f"Chipload {chipload:g} exceeds {mat.label} conservative high "
                f"{high:g} mm/tooth."))

    if flutes <= 0:
        raise ValueError("flutes must be a positive integer.")
    if spindle_rpm <= 0:
        raise ValueError("spindle_rpm must be positive.")
    if tool_diameter_mm <= 0:
        warnings.append("Tool diameter is zero/negative; surface speed is not meaningful.")
        diagnostics.append(FeedDiagnostic(
            MISSING_DIAMETER_OR_SPEED, "warning",
            "Tool diameter is missing or non-positive; geometry-derived values "
            "are not meaningful."))
    if max_rpm is not None and spindle_rpm > max_rpm:
        warnings.append(
            f"Spindle {spindle_rpm:g} RPM exceeds the machine maximum {max_rpm:g} RPM."
        )
        diagnostics.append(FeedDiagnostic(
            RPM_EXCEEDS_MACHINE_LIMIT, "danger",
            f"Spindle {spindle_rpm:g} RPM exceeds the machine maximum {max_rpm:g} RPM."))

    computed_feed = spindle_rpm * flutes * chipload
    surface_speed = math.pi * tool_diameter_mm * spindle_rpm

    feed_rate = computed_feed
    if feed_override is not None:
        feed_rate = feed_override
        notes.append(f"Feed overridden to {feed_override:g} mm/min (computed {computed_feed:g}).")

    # --- Engagement-dependent advisory values (WOC/DOC) --------------------- #
    thinning = _chip_thinning_factor(tool_diameter_mm, woc_mm)
    mrr: Optional[float] = None
    power_w: Optional[float] = None
    power_kw: Optional[float] = None
    power_hp: Optional[float] = None
    torque_nm: Optional[float] = None

    if woc_mm is not None and tool_diameter_mm > 0 and woc_mm > tool_diameter_mm:
        diagnostics.append(FeedDiagnostic(
            WOC_EXCEEDS_DIAMETER, "danger",
            f"Width of cut {woc_mm:g} mm exceeds tool diameter "
            f"{tool_diameter_mm:g} mm."))
    if doc_mm is not None and tool_diameter_mm > 0 and doc_mm > tool_diameter_mm:
        diagnostics.append(FeedDiagnostic(
            DOC_AGGRESSIVE, "warning",
            f"Depth of cut {doc_mm:g} mm exceeds tool diameter "
            f"{tool_diameter_mm:g} mm (aggressive)."))

    if woc_mm is not None and doc_mm is not None and woc_mm > 0 and doc_mm > 0:
        mrr = woc_mm * doc_mm * feed_rate
        ks = specific_energy_j_mm3
        if ks is None:
            ks = _SPECIFIC_ENERGY_J_MM3.get(material, _DEFAULT_SPECIFIC_ENERGY_J_MM3)
        power_w = (mrr / 60.0) * ks
        power_kw = power_w / 1000.0
        power_hp = power_kw * _HP_PER_KW
        torque_nm = power_w * 60.0 / (2.0 * math.pi * spindle_rpm)
        notes.append(
            f"Advisory power/torque from specific energy {ks:g} J/mm^3 — "
            "order-of-magnitude only.")
        if max_power_kw is not None and power_kw > max_power_kw:
            diagnostics.append(FeedDiagnostic(
                POWER_EXCEEDS_MACHINE_LIMIT, "danger",
                f"Estimated spindle power {power_kw:.3g} kW exceeds machine "
                f"limit {max_power_kw:g} kW."))

    return FeedRecommendation(
        rpm=round_for_gcode(spindle_rpm, 3),
        feed_rate=round_for_gcode(feed_rate, 3),
        chipload=round_for_gcode(chipload, 4),
        surface_speed=round_for_gcode(surface_speed, 3),
        chip_thinning_factor=round_for_gcode(thinning, 4),
        material_removal_rate=None if mrr is None else round_for_gcode(mrr, 3),
        spindle_power_kw=None if power_kw is None else round_for_gcode(power_kw, 4),
        spindle_power_hp=None if power_hp is None else round_for_gcode(power_hp, 4),
        torque_nm=None if torque_nm is None else round_for_gcode(torque_nm, 4),
        power_w=None if power_w is None else round_for_gcode(power_w, 3),
        notes=notes,
        warnings=warnings,
        diagnostics=diagnostics,
    )
