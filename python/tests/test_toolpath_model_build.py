"""CS-003 canonical preview bridge: build_toolpath_model / ToolpathSegment.

The legacy model_from_moves stays covered by test_preview_model.py; this file
exercises the richer segment shape and the parsed-program entry point.
"""

import math

import pytest

from cam_creation_studio.gcode.parser import parse_program_model
from cam_creation_studio.preview.toolpath_model import (
    ARC,
    BURN,
    CUT,
    EXTRUDE,
    TRAVEL,
    ToolpathSegment,
    build_toolpath_model,
)

PROGRAM = """\
G21
G0 Z5
G1 Z-1 F400
G1 X30 Y0 F800
G2 X40 Y10 I0 J10 F800
M30
"""


def test_build_from_text_returns_toolpath_segments():
    segs = build_toolpath_model(PROGRAM)
    assert segs and all(isinstance(s, ToolpathSegment) for s in segs)


def test_g0_is_travel_with_no_feed():
    segs = build_toolpath_model([{"type": "G0", "x": "10", "y": "0", "z": "5"}])
    assert segs[0].type == TRAVEL
    assert segs[0].feed is None
    assert segs[0].source_command == "G0"


def test_g1_negative_z_is_cut():
    segs = build_toolpath_model([{"type": "G1", "x": "10", "z": "-0.5", "f": "300"}])
    assert segs[0].type == CUT
    assert segs[0].end.z == -0.5 and segs[0].z == -0.5
    assert segs[0].feed == 300


def test_g1_with_e_is_extrude():
    segs = build_toolpath_model([{"type": "G1", "x": "10", "e": "2", "f": "1500"}])
    assert segs[0].type == EXTRUDE


def test_arc_is_a_single_arc_segment():
    segs = build_toolpath_model(PROGRAM)
    arcs = [s for s in segs if s.type == ARC]
    assert len(arcs) == 1
    # quarter circle, radius 10 -> arc length pi*10/2
    assert arcs[0].distance == pytest.approx(math.pi * 10 / 2, rel=1e-3)
    assert arcs[0].source_command == "G2"


def test_distance_is_populated():
    segs = build_toolpath_model([{"type": "G1", "x": "3", "y": "4", "f": "500"}])
    assert segs[0].distance == 5.0


def test_line_number_is_preserved_from_program():
    program = parse_program_model(PROGRAM)
    segs = build_toolpath_model(program)
    # every segment carries a source line, strictly increasing with the moves
    lines = [s.line for s in segs]
    assert all(isinstance(n, int) for n in lines)
    assert lines == sorted(lines)


def test_laser_flag_forces_burn():
    segs = build_toolpath_model([{"type": "G1", "x": "10", "f": "600"}], laser=True)
    assert segs[0].type == BURN


def test_frm_to_parity_with_segment():
    segs = build_toolpath_model([{"type": "G1", "x": "10", "f": "600"}])
    s = segs[0]
    assert s.frm is s.start and s.to is s.end and s.source_line == s.line
