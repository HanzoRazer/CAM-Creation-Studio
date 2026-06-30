from cam_creation_studio.gcode.generator import (
    build_header,
    build_manual_body,
    build_etch_body,
    build_footer,
    build_program,
)
from cam_creation_studio.gcode.dialects import get_dialect, list_dialects

CNC = {
    "machine": "genericCnc", "units": "mm", "positioning": "abs",
    "home": True, "spindleOn": True, "spindleRpm": 12000, "safeZ": 5,
}
MARLIN = {
    "machine": "marlin", "units": "mm", "positioning": "abs",
    "home": True, "hotend": 210, "bed": 60, "safeZ": 5,
}


def text(lines):
    return "\n".join(lines)


def test_cnc_header_contains_expected():  # Test 1
    out = text(build_header(CNC))
    for expected in ["G21", "G90", "G28", "M3 S12000", "G0 Z5"]:
        assert expected in out


def test_marlin_header_heater_sequence():  # Test 2
    out = text(build_header(MARLIN))
    for expected in ["G21", "G90", "M140", "M104", "M190", "M109"]:
        assert expected in out


def test_inch_units_declared_as_g20():
    out = text(build_header({**CNC, "units": "in"}))
    assert "G20" in out and "G21" not in out


def test_home_omitted_when_false():
    assert "G28" not in text(build_header({**CNC, "home": False}))


def test_cnc_footer():  # Test 3
    out = text(build_footer(CNC))
    for expected in ["G0 Z5", "M5", "G0 X0 Y0", "M30"]:
        assert expected in out


def test_marlin_footer_shutdown():
    out = text(build_footer(MARLIN))
    for expected in ["M104 S0", "M140 S0", "M84", "M30"]:
        assert expected in out


def test_arc_move_emits_ij():  # Test 4
    moves = [{"type": "G2", "x": "10", "y": "10", "i": "5", "j": "0"}]
    assert "G2 X10 Y10 I5 J0" in text(build_manual_body(moves, CNC))


def test_extruder_only_on_marlin():
    moves = [{"type": "G1", "x": "40", "z": "-0.5", "f": "800", "e": "2"}]
    assert "E2" not in text(build_manual_body(moves, CNC))
    assert "E2" in text(build_manual_body(moves, MARLIN))


def test_etch_power_strategy():
    cfg = {"machine": "laserGrbl", "safeZ": 5, "etch": {"control": "power", "feed": 600, "power": 200}}
    out = text(build_etch_body([{"poly": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]}], cfg))
    assert "M3 S200" in out and "M5" in out and "F600" in out


def test_etch_depth_strategy():
    cfg = {"machine": "genericCnc", "safeZ": 5, "etch": {"control": "depth", "feed": 600, "engraveZ": -0.2}}
    out = text(build_etch_body([{"poly": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]}], cfg))
    assert "G1 Z-0.2 F300" in out and "G0 Z5" in out


def test_etch_no_regions_note():
    cfg = {"machine": "laserGrbl", "safeZ": 5, "etch": {"control": "power"}}
    assert "no burn regions" in text(build_etch_body([], cfg))


def test_build_program_orders_sections():
    program = build_program(CNC, {"mode": "manual", "moves": [{"type": "G1", "x": "10", "f": "800"}]})
    assert program.index("HEADER") < program.index("BODY") < program.index("FOOTER")


def test_dialect_alias_and_unknown():
    assert get_dialect("cnc").id == "genericCnc"
    try:
        get_dialect("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_dialect_registry():
    assert sorted(d.id for d in list_dialects()) == ["genericCnc", "laserGrbl", "marlin"]
