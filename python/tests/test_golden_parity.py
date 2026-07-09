"""Golden-parity tests: lock the generator's exact output.

These fixtures freeze the current G-code the generator produces for a canonical
CNC square, Marlin square, and laser/etch job. A refactor that changes output
byte-for-byte must update the fixture deliberately (and justify it in review),
which is exactly the point: silent formatting drift becomes a failing test.

Only line endings are normalized (CRLF -> LF); whitespace is compared exactly.
To regenerate after an intentional generator change, run this module directly:

    python tests/test_golden_parity.py --write
"""

import sys
from pathlib import Path

from cam_creation_studio.gcode.generator import build_program

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


def _norm(text: str) -> str:
    """Normalize line endings only — never whitespace."""
    return text.replace("\r\n", "\n")


# --- Canonical programs (the single source of truth for the fixtures) -------

_SQUARE_MOVES = [
    {"type": "G0", "x": 0, "y": 0, "z": 5},
    {"type": "G0", "x": 0, "y": 0},
    {"type": "G1", "z": -1, "f": 800},
    {"type": "G1", "x": 40, "f": 800},
    {"type": "G1", "y": 40, "f": 800},
    {"type": "G1", "x": 0, "f": 800},
    {"type": "G1", "y": 0, "f": 800},
    {"type": "G0", "z": 5},
]


def cnc_square_text() -> str:
    config = {"machine": "genericCnc", "units": "mm", "positioning": "abs",
              "safeZ": 5, "spindleOn": True, "spindleRpm": 12000}
    return build_program(config, {"mode": "manual", "moves": _SQUARE_MOVES})


def marlin_square_text() -> str:
    config = {"machine": "marlin", "units": "mm", "positioning": "abs",
              "safeZ": 5, "home": True, "bed": 60, "hotend": 200}
    moves = [
        {"type": "G0", "x": 0, "y": 0, "z": 5},
        {"type": "G1", "x": 40, "y": 0, "e": 2, "f": 1500},
        {"type": "G1", "x": 40, "y": 40, "e": 4, "f": 1500},
        {"type": "G1", "x": 0, "y": 40, "e": 6, "f": 1500},
        {"type": "G1", "x": 0, "y": 0, "e": 8, "f": 1500},
        {"type": "G0", "z": 5},
    ]
    return build_program(config, {"mode": "manual", "moves": moves})


def laser_etch_text() -> str:
    config = {"machine": "laser", "units": "mm", "positioning": "abs", "safeZ": 5,
              "etch": {"control": "power", "feed": 600, "power": 200}}
    paths = [{"poly": [{"x": 0, "y": 0}, {"x": 10, "y": 0},
                       {"x": 10, "y": 10}, {"x": 0, "y": 10}, {"x": 0, "y": 0}]}]
    return build_program(config, {"mode": "etch", "paths": paths})


_FIXTURES = {
    "simple_cnc_square.gcode": cnc_square_text,
    "simple_marlin_square.gcode": marlin_square_text,
    "simple_laser_etch.gcode": laser_etch_text,
}


# --- Tests ------------------------------------------------------------------

def test_cnc_square_matches_golden():
    assert _norm(cnc_square_text()) == _norm(read_golden("simple_cnc_square.gcode"))


def test_marlin_square_matches_golden():
    assert _norm(marlin_square_text()) == _norm(read_golden("simple_marlin_square.gcode"))


def test_laser_etch_matches_golden():
    assert _norm(laser_etch_text()) == _norm(read_golden("simple_laser_etch.gcode"))


def _write_fixtures() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in _FIXTURES.items():
        (GOLDEN_DIR / name).write_text(builder(), encoding="utf-8", newline="\n")
        print(f"wrote {name}")


if __name__ == "__main__":
    if "--write" in sys.argv:
        _write_fixtures()
    else:
        print("pass --write to (re)generate golden fixtures")
