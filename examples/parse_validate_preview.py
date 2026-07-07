"""Example: the full analysis pipeline on a chunk of G-code text.

    G-code text -> parse -> validate (Diagnostics) -> toolpath model (segments)

This is the "execution-analysis" half of the core: take a program you did not
author and make it inspectable.

Run directly::

    python examples/parse_validate_preview.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.gcode.parser import parse_program_model  # noqa: E402
from cam_creation_studio.gcode.validator import validate_program  # noqa: E402
from cam_creation_studio.preview.toolpath_model import build_toolpath_model  # noqa: E402

PROGRAM = """\
G21
G90
G0 Z5
G0 X0 Y0
G1 Z-1 F400
G1 X30 Y0 F800
G2 X40 Y10 I0 J10 F800
G1 X40 Y40
G0 Z5
M30
"""

MACHINE = "genericCnc"


def main() -> None:
    print("=== Program ===")
    print(PROGRAM)

    print("=== Diagnostics ===")
    diagnostics = validate_program(PROGRAM, MACHINE)
    if not diagnostics:
        print("(none)")
    for d in diagnostics:
        where = f" (line {d.line})" if d.line else ""
        print(f"[{d.severity.value:>7}] {d.code}{where}: {d.message}")

    print("\n=== Toolpath model ===")
    program = parse_program_model(PROGRAM)
    segments = build_toolpath_model(program)
    total = 0.0
    for s in segments:
        total += s.distance
        feed = f"F{s.feed:g}" if s.feed else "-"
        print(f"{s.source_command:>3} {s.type:<7} "
              f"({s.start.x:g},{s.start.y:g},{s.start.z:g}) -> "
              f"({s.end.x:g},{s.end.y:g},{s.end.z:g})  "
              f"{feed}  d={s.distance:.3f}")
    print(f"\nsegments: {len(segments)}   total path length: {total:.3f} mm")


if __name__ == "__main__":
    main()
