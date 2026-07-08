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
    # G2 from (30,0) to (40,10) about center (30,10): clockwise, the sweep is the
    # 270-degree long way, not the 90-degree counter-clockwise short way.
    assert arcs[0].distance == pytest.approx(3 * math.pi * 10 / 2, rel=1e-3)
    assert arcs[0].source_command == "G2"


def _arc_seg(moves):
    segs = build_toolpath_model(moves)
    arcs = [s for s in segs if s.type == ARC]
    assert len(arcs) == 1
    return arcs[0]


# Each arc below is centered on (0,0) via I/J relative to a start on the +X axis
# at radius 10, so the expected lengths are exact fractions of 2*pi*10.

def test_g2_clockwise_quarter_arc():
    # (10,0) -> (0,-10) clockwise is the 90-degree short way through (7,-7).
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G2", "x": "0", "y": "-10", "i": "-10", "j": "0"}])
    assert arc.distance == pytest.approx(math.pi * 10 / 2, rel=1e-6)


def test_g3_counter_clockwise_quarter_arc():
    # (10,0) -> (0,10) counter-clockwise is the 90-degree short way through (7,7).
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G3", "x": "0", "y": "10", "i": "-10", "j": "0"}])
    assert arc.distance == pytest.approx(math.pi * 10 / 2, rel=1e-6)


def test_g2_reflex_large_sweep_arc():
    # (10,0) -> (0,10) clockwise is the 270-degree long way (through the bottom).
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G2", "x": "0", "y": "10", "i": "-10", "j": "0"}])
    assert arc.distance == pytest.approx(3 * math.pi * 10 / 2, rel=1e-6)
    # A clockwise (negative) sweep must still produce a positive length.
    assert arc.distance > 0


def test_g3_reflex_large_sweep_arc():
    # (10,0) -> (0,-10) counter-clockwise is the 270-degree long way (through the top).
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G3", "x": "0", "y": "-10", "i": "-10", "j": "0"}])
    assert arc.distance == pytest.approx(3 * math.pi * 10 / 2, rel=1e-6)


def test_direction_not_silently_using_ccw_sweep():
    # Same endpoints and center, opposite directions must give different lengths
    # that sum to the full circle. The old code returned the CCW sweep for both,
    # so the G2 value would wrongly equal the G3 (short) value.
    start = {"type": "G0", "x": "10", "y": "0"}
    g2 = _arc_seg([start, {"type": "G2", "x": "0", "y": "10", "i": "-10", "j": "0"}])
    g3 = _arc_seg([start, {"type": "G3", "x": "0", "y": "10", "i": "-10", "j": "0"}])
    assert g2.distance != pytest.approx(g3.distance, rel=1e-6)
    assert g2.distance + g3.distance == pytest.approx(2 * math.pi * 10, rel=1e-6)
    # G2 here is the long way; it must not collapse to the CCW quarter length.
    assert g2.distance == pytest.approx(3 * math.pi * 10 / 2, rel=1e-6)


def test_full_circle_arc_preserves_two_pi_sweep():
    # start == end with an I/J center is a full circle in either direction.
    g2 = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                   {"type": "G2", "x": "10", "y": "0", "i": "-10", "j": "0"}])
    g3 = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                   {"type": "G3", "x": "10", "y": "0", "i": "-10", "j": "0"}])
    assert g2.distance == pytest.approx(2 * math.pi * 10, rel=1e-6)
    assert g3.distance == pytest.approx(2 * math.pi * 10, rel=1e-6)


def test_near_full_circle_is_almost_two_pi_not_tiny():
    # End one hundredth of a radian short of the start, swept the long way round.
    ang = -0.01
    ex, ey = 10 * math.cos(ang), 10 * math.sin(ang)
    # G3 (CCW) from angle 0 must go nearly all the way around, not a tiny hop.
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G3", "x": str(ex), "y": str(ey), "i": "-10", "j": "0"}])
    full = 2 * math.pi * 10
    assert arc.distance == pytest.approx(full - 0.1, rel=1e-3)
    assert arc.distance < full


# --- R-mode arcs (no I/J center) --------------------------------------------
# (10,0) -> (0,10): chord = sqrt(200); with radius 10 the minor arc is 90 deg.

def test_r_positive_is_minor_arc():
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G2", "x": "0", "y": "10", "r": "10"}])
    assert arc.distance == pytest.approx(math.pi * 10 / 2, rel=1e-6)


def test_r_negative_is_major_arc():
    # Negative R selects the >180-degree (270-degree here) arc.
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G3", "x": "0", "y": "10", "r": "-10"}])
    assert arc.distance == pytest.approx(3 * math.pi * 10 / 2, rel=1e-6)


def test_r_arc_no_longer_falls_back_to_chord():
    # The chord here is sqrt(200) ~ 14.14; the real minor arc is ~15.71.
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G2", "x": "0", "y": "10", "r": "10"}])
    chord = math.hypot(10, 10)
    assert arc.distance > chord
    assert arc.distance == pytest.approx(math.pi * 10 / 2, rel=1e-6)


def test_arc_without_center_or_radius_falls_back_to_chord():
    arc = _arc_seg([{"type": "G0", "x": "10", "y": "0"},
                    {"type": "G2", "x": "0", "y": "10"}])
    assert arc.distance == pytest.approx(math.hypot(10, 10), rel=1e-9)


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
