"""Example: advisory feeds/speeds against a machine profile.

Computes a starting-point recommendation for a cut, bounded by a machine
profile's RPM/power ceiling, and prints the canonical ``FeedRecommendation``
plus its coded diagnostics.

Everything here is ADVISORY — a starting point that requires operator
verification, never a certified value.

Run directly::

    python examples/feeds_speeds_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.feeds_speeds.calculator import calculate_feeds  # noqa: E402
from cam_creation_studio.feeds_speeds.machines import get_machine  # noqa: E402

MATERIAL = "aluminum"
TOOL_DIA = 6.0     # mm
FLUTES = 2
RPM = 18000.0
WOC = 1.5          # mm width of cut
DOC = 6.0          # mm depth of cut


def main() -> None:
    machine = get_machine("genericCncRouter")
    # A router with a 9 kW ceiling would be generous; use a small hobby bound.
    max_power_kw = 1.5

    rec = calculate_feeds(
        tool_diameter_mm=TOOL_DIA,
        flutes=FLUTES,
        spindle_rpm=RPM,
        material=MATERIAL,
        woc_mm=WOC,
        doc_mm=DOC,
        max_rpm=machine.max_rpm,
        max_power_kw=max_power_kw,
    )

    print(f"Material: {MATERIAL}   Tool: {TOOL_DIA:g} mm, {FLUTES} flute   "
          f"Machine: {machine.label}")
    print("-" * 60)
    print(f"RPM                 : {rec.rpm:g}")
    print(f"Feed rate           : {rec.feed_rate:g} mm/min")
    print(f"Chipload            : {rec.chipload:g} mm/tooth")
    print(f"Surface speed       : {rec.surface_speed_m_min:g} m/min")
    print(f"Chip-thinning factor: {rec.chip_thinning_factor:g}")
    print(f"Material removal    : {rec.material_removal_rate} mm^3/min")
    print(f"Spindle power (est.) : {rec.spindle_power_kw} kW / {rec.spindle_power_hp} hp")
    print(f"Torque (est.)       : {rec.torque_nm} Nm")

    print("\nDiagnostics:")
    for d in rec.diagnostics:
        print(f"  [{d.severity:>7}] {d.code}: {d.message}")


if __name__ == "__main__":
    main()
