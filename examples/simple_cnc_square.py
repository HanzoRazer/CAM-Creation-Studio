"""Example: generate a simple CNC square from the typed domain model.

Builds a :class:`GCodeProgram` (header + moves + footer), renders it to G-code
text, and prints it. This is the "author" half of the core.

Run directly::

    python examples/simple_cnc_square.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable when running from a source checkout (no install).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from cam_creation_studio.enums import MoveType, Units  # noqa: E402
from cam_creation_studio.gcode.generator import program_to_text  # noqa: E402
from cam_creation_studio.models import (  # noqa: E402
    GCodeProgram,
    Move,
    ProgramFooter,
    ProgramHeader,
)

SIDE = 40.0     # mm
FEED = 800.0    # mm/min
SAFE_Z = 5.0    # mm
CUT_Z = -1.0    # mm


def build_square() -> GCodeProgram:
    """A 40 mm square cut at Z=-1 on a generic CNC router."""
    header = ProgramHeader(
        units=Units.MM, absolute=True, machine="genericCnc",
        safe_z=SAFE_Z, spindle_on=True, spindle_rpm=12000,
        comment="Simple CNC square demo",
    )
    moves = [
        Move(MoveType.RAPID, x=0.0, y=0.0, z=SAFE_Z),
        Move(MoveType.RAPID, x=0.0, y=0.0),
        Move(MoveType.LINEAR, z=CUT_Z, feed=FEED),
        Move(MoveType.LINEAR, x=SIDE, feed=FEED),
        Move(MoveType.LINEAR, y=SIDE, feed=FEED),
        Move(MoveType.LINEAR, x=0.0, feed=FEED),
        Move(MoveType.LINEAR, y=0.0, feed=FEED),
        Move(MoveType.RAPID, z=SAFE_Z),
    ]
    footer = ProgramFooter(units=Units.MM, machine="genericCnc", safe_z=SAFE_Z, end_code="M30")
    return GCodeProgram(header=header, moves=moves, footer=footer)


def main() -> None:
    program = build_square()
    print(program_to_text(program))
    b = program.bounds()
    if b is not None:
        print(f"\n; bounds: {b.width:g} x {b.height:g} mm (XY)")


if __name__ == "__main__":
    main()
