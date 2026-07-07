"""CS-003 canonical validator codes: cross-dialect contamination, UNKNOWN_GCODE,
and the alias-aware has_code helper."""

from cam_creation_studio.gcode.validator import (
    CANONICAL_CODES,
    codes,
    has_code,
    validate_program,
)


def code_set(text, machine=None):
    return {d.code for d in validate_program(text, machine)}


# ---- canonical vocabulary ----
def test_eleven_canonical_codes_declared():
    assert len(CANONICAL_CODES) == 11
    for name in (
        "EMPTY_PROGRAM", "UNITS_NOT_DECLARED", "CUT_WITHOUT_FEED",
        "ARC_WITHOUT_CENTER_OR_RADIUS", "EXTRUDER_WORD_IN_CNC",
        "HEATER_COMMAND_IN_CNC", "SPINDLE_COMMAND_IN_FDM",
        "MARLIN_COMMAND_IN_GRBL", "NO_FOOTER_SHUTDOWN", "MISSING_SAFE_Z",
        "UNKNOWN_GCODE",
    ):
        assert name in CANONICAL_CODES


def test_empty_program_alias_resolves():
    diags = validate_program("G21\n; nothing here\n", "genericCnc")
    # legacy code still emitted...
    assert "EMPTY_PROGRAM_BODY" in {d.code for d in diags}
    # ...and the canonical name resolves through has_code
    assert has_code(diags, "EMPTY_PROGRAM")
    assert codes.canonical_code("EMPTY_PROGRAM_BODY") == "EMPTY_PROGRAM"


# ---- cross-dialect contamination ----
def test_extruder_word_in_cnc():
    assert "EXTRUDER_WORD_IN_CNC" in code_set(
        "G21\nG0 Z5\nG1 X5 E1 F100\nM30\n", "genericCnc")


def test_heater_command_in_cnc():
    assert "HEATER_COMMAND_IN_CNC" in code_set(
        "G21\nM104 S200\nG0 Z5\nG1 X5 F100\nM3 S1\nM30\n", "genericCnc")


def test_spindle_command_in_fdm():
    assert "SPINDLE_COMMAND_IN_FDM" in code_set(
        "G21\nM104 S200\nM3 S1000\nG0 Z5\nG1 X5 E1 F100\nM30\n", "marlin")


def test_marlin_command_in_grbl():
    assert "MARLIN_COMMAND_IN_GRBL" in code_set(
        "G21\nM104 S200\nG0 Z5\nG1 X5 E1 F100\nM30\n", "laserGrbl")


def test_grbl_rejects_marlin_heater_and_extruder():
    c = code_set("G21\nM140 S60\nG0 Z5\nG1 X5 E1 F100\nM30\n", "laserGrbl")
    assert "MARLIN_COMMAND_IN_GRBL" in c


def test_clean_cnc_has_no_contamination():
    c = code_set("G21\nG0 Z5\nM3 S12000\nG1 X10 F800\nG0 Z5\nM5\nM30\n", "genericCnc")
    assert "EXTRUDER_WORD_IN_CNC" not in c
    assert "HEATER_COMMAND_IN_CNC" not in c
    assert "SPINDLE_COMMAND_IN_FDM" not in c


# ---- unknown g-code ----
def test_unknown_gcode_flagged():
    assert "UNKNOWN_GCODE" in code_set("G21\nG0 Z5\nG99 X1\nM30\n", "genericCnc")


def test_known_gcodes_not_flagged():
    c = code_set("G21\nG90\nG0 Z5\nG1 X10 F100\nG2 X20 Y0 I5 J0 F100\nM30\n", "genericCnc")
    assert "UNKNOWN_GCODE" not in c
