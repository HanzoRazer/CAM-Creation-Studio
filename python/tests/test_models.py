import pytest

from cam_creation_studio.enums import DiagnosticSeverity, MoveType, Units
from cam_creation_studio.models import (
    ArcMove,
    Bounds,
    Diagnostic,
    FeedRecommendation,
    GCodeProgram,
    MachineProfile,
    Material,
    Move,
    Point,
    ProgramFooter,
    ProgramHeader,
    Tool,
    move_from_dict,
)
from cam_creation_studio.shared.serialization import from_json, to_json


# ---- construction + equality ----
def test_move_equality_and_defaults():
    assert Move(x=10, y=5) == Move(type=MoveType.LINEAR, x=10, y=5)
    assert Move(x=10) != Move(x=11)
    assert not Move().is_arc


def test_arcmove_requires_arc_type():
    a = ArcMove(type=MoveType.ARC_CCW, x=1, y=1, i=1, j=0)
    assert a.is_arc and not a.clockwise
    with pytest.raises(ValueError):
        ArcMove(type=MoveType.LINEAR, x=1, y=1)


def test_diagnostic_normalizes_severity():
    d = Diagnostic("danger", "CODE", "msg", 4)  # plain string coerced to enum
    assert d.severity is DiagnosticSeverity.DANGER
    assert d.severity == "danger"
    assert d.as_dict() == {"severity": "danger", "code": "CODE", "message": "msg", "line": 4}


def test_program_header_footer_defaults():
    assert ProgramHeader().units is Units.MM
    assert ProgramFooter().end_code == "M30"


def test_gcode_program_bounds():
    prog = GCodeProgram(moves=[Move(x=0, y=0), Move(x=10, y=20), ArcMove(x=5, y=-5, i=1, j=1)])
    assert prog.bounds() == Bounds(0.0, -5.0, 10.0, 20.0, 0.0, 0.0)


def test_empty_program_bounds_is_none():
    assert GCodeProgram().bounds() is None


# ---- serialization ----
@pytest.mark.parametrize("obj", [
    Move(type=MoveType.LINEAR, x=10, y=5, feed=800, comment="cut"),
    ArcMove(type=MoveType.ARC_CW, x=10, y=10, i=5, j=0, feed=400),
    Diagnostic(DiagnosticSeverity.WARNING, "C", "m", 2),
    ProgramHeader(units=Units.INCH, home=True, spindle_rpm=12000),
    ProgramFooter(units=Units.MM, spindle_on=True),
    Point(1.0, 2.0, 3.0),
    Bounds(0, 0, 10, 10),
])
def test_generic_roundtrip(obj):
    restored = from_json(type(obj), to_json(obj))
    assert restored == obj


def test_gcode_program_json_roundtrip():
    prog = GCodeProgram(
        header=ProgramHeader(units=Units.MM, home=True),
        moves=[Move(x=10, y=0, feed=800), ArcMove(x=10, y=10, i=5, j=0)],
        footer=ProgramFooter(end_code="M2"),
    )
    restored = GCodeProgram.from_json(prog.to_json())
    assert restored == prog


def test_move_from_dict_picks_type():
    assert isinstance(move_from_dict({"type": "G1", "x": "10"}), Move)
    assert isinstance(move_from_dict({"type": "G2", "x": "1", "i": "2", "j": "0"}), ArcMove)
    # arc inferred from I/J even when type says G1
    assert isinstance(move_from_dict({"type": "G1", "i": "2", "j": "0"}), ArcMove)


# ---- re-exported profile objects still construct ----
def test_profile_objects_construct():
    assert MachineProfile(id="m", label="M").id == "m"
    assert Material("x", "X", (0.05, 0.1)).chipload_mid == pytest.approx(0.075)
    assert Tool("t", "T", 6.0, 2, "endmill").diameter_mm == 6.0
    assert FeedRecommendation(rpm=1, feed_rate=2, chipload=0.1, surface_speed=3).feed_rate == 2
