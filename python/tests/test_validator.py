from cam_creation_studio.gcode.validator import validate_program


def codes(text, machine=None):
    return {w.code for w in validate_program(text, machine)}


def test_cut_without_feed():  # Test 5
    assert "CUT_WITHOUT_FEED" in codes("G21\nG0 Z5\nG1 X10 Y10\nM30\n", "genericCnc")


def test_spindle_off_with_cuts():  # Test 6
    prog = "G21\nG0 Z5\nG1 X10 Y10 F800\nG0 Z5\nM30\n"
    assert "SPINDLE_OFF_WITH_CUTS" in codes(prog, "genericCnc")


def test_spindle_present_no_warning():
    prog = "G21\nG0 Z5\nM3 S12000\nG1 X10 Y10 F800\nM5\nM30\n"
    assert "SPINDLE_OFF_WITH_CUTS" not in codes(prog, "genericCnc")


def test_arc_without_center_or_radius():  # Test 7
    prog = "G21\nG0 Z5\nG1 X0 Y0 F100\nG2 X10 Y10\nM30\n"
    assert "ARC_WITHOUT_CENTER_OR_RADIUS" in codes(prog, "genericCnc")


def test_arc_with_ij_ok():
    prog = "G21\nG0 Z5\nG1 X0 Y0 F100\nG2 X10 Y10 I5 J0\nM30\n"
    assert "ARC_WITHOUT_CENTER_OR_RADIUS" not in codes(prog, "genericCnc")


def test_units_not_declared():  # Test 8
    assert "UNITS_NOT_DECLARED" in codes("G0 Z5\nG1 X10 F100\nM30\n", "genericCnc")


def test_units_declared_ok():
    assert "UNITS_NOT_DECLARED" not in codes("G21\nG0 Z5\nG1 X10 F100\nM30\n", "genericCnc")


def test_missing_safe_z():
    assert "MISSING_SAFE_Z" in codes("G21\nG1 X10 F100\nM30\n", "genericCnc")


def test_no_footer_shutdown():
    assert "NO_FOOTER_SHUTDOWN" in codes("G21\nG0 Z5\nG1 X10 F100\n", "genericCnc")


def test_empty_program_body():
    assert "EMPTY_PROGRAM_BODY" in codes("G21\n; nothing here\n", "genericCnc")


def test_extrusion_without_hotend():
    prog = "G21\nG0 Z5\nG1 X10 E2 F100\nM30\n"
    assert "EXTRUSION_WITHOUT_HOTEND" in codes(prog, "marlin")


def test_extrusion_with_hotend_ok():
    prog = "G21\nM104 S210\nM109 S210\nG0 Z5\nG1 X10 E2 F100\nM30\n"
    assert "EXTRUSION_WITHOUT_HOTEND" not in codes(prog, "marlin")


def test_negative_z_in_laser_mode():
    prog = "G21\nG0 Z5\nG1 X10 Z-1 F100\nM30\n"
    assert "NEGATIVE_Z_IN_LASER_MODE" in codes(prog, "laserGrbl")


def test_warning_has_severity_and_dict():
    warnings = validate_program("G0 Z5\nG1 X10\n")
    assert all(w.severity in ("info", "warning", "danger") for w in warnings)
    assert warnings[0].as_dict()["code"]
