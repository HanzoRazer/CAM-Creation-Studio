"""Object-path generation: typed GCodeProgram renders identically to the dict
adapter, and generated bodies round-trip back through the parser."""

from cam_creation_studio.enums import MoveType
from cam_creation_studio.gcode.body import body_lines_from_moves
from cam_creation_studio.gcode.formatter import render
from cam_creation_studio.gcode.generator import (
    build_program,
    program_from_config,
    program_to_text,
)
from cam_creation_studio.gcode.parser import parse_moves
from cam_creation_studio.models import ArcMove, Move

CNC = {
    "machine": "genericCnc", "units": "mm", "positioning": "abs",
    "home": True, "spindleOn": True, "spindleRpm": 12000, "safeZ": 5,
}
MARLIN = {
    "machine": "marlin", "units": "mm", "positioning": "abs",
    "home": True, "hotend": 210, "bed": 60, "safeZ": 5,
}


def test_object_path_matches_dict_path_cnc():
    moves = [Move(type=MoveType.LINEAR, x=10, y=0, feed=800),
             ArcMove(type=MoveType.ARC_CW, x=10, y=10, i=5, j=0)]
    dict_moves = [{"type": "G1", "x": 10, "y": 0, "f": 800},
                  {"type": "G2", "x": 10, "y": 10, "i": 5, "j": 0}]
    obj_out = program_to_text(program_from_config(CNC, moves))
    dict_out = build_program(CNC, {"mode": "manual", "moves": dict_moves})
    assert obj_out == dict_out


def test_object_path_marlin_extrusion():
    moves = [Move(type=MoveType.LINEAR, x=40, z=-0.5, feed=800, e=2)]
    out = program_to_text(program_from_config(MARLIN, moves))
    assert "E2" in out
    assert "M140" in out and "M104" in out  # heater startup from dialect


def test_body_roundtrips_through_parser():
    moves = [
        Move(type=MoveType.LINEAR, x=10.0, y=0.0, feed=800.0),
        Move(type=MoveType.LINEAR, x=20.0, z=-0.5),
        ArcMove(type=MoveType.ARC_CW, x=10.0, y=10.0, i=5.0, j=0.0, feed=400.0),
        Move(type=MoveType.RAPID, x=0.0, y=0.0),
    ]
    text = "\n".join(render(ln) for ln in body_lines_from_moves(moves))
    assert parse_moves(text) == moves
