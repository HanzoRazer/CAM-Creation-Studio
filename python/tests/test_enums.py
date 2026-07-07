from cam_creation_studio.enums import (
    CutMode,
    DiagnosticSeverity,
    MachineType,
    MoveType,
    Units,
)


def test_enums_are_str_valued():
    # str-based so they compare equal to and serialize as their wire value.
    assert Units.MM == "mm"
    assert MoveType.LINEAR == "G1"
    assert DiagnosticSeverity.DANGER == "danger"
    assert CutMode.POWER == "power"
    assert MachineType.CNC == "genericCnc"


def test_units_gcode_word():
    assert Units.MM.gcode_word == "G21"
    assert Units.INCH.gcode_word == "G20"


def test_movetype_arc_and_cut():
    assert MoveType.ARC_CW.is_arc and MoveType.ARC_CCW.is_arc
    assert not MoveType.LINEAR.is_arc and not MoveType.RAPID.is_arc
    assert MoveType.LINEAR.is_cut and MoveType.ARC_CW.is_cut
    assert not MoveType.RAPID.is_cut


def test_construct_from_value():
    assert MoveType("G2") is MoveType.ARC_CW
    assert DiagnosticSeverity("info") is DiagnosticSeverity.INFO
