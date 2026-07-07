from cam_creation_studio.enums import MoveType, Units
from cam_creation_studio.gcode.parser import (
    move_from_line,
    parse_line,
    parse_moves,
    parse_program_model,
)
from cam_creation_studio.models import ArcMove, Move


def test_move_from_line_linear():
    m = move_from_line(parse_line("G1 X10 Y5 F800 ; cut"))
    assert isinstance(m, Move)
    assert m.type is MoveType.LINEAR
    assert (m.x, m.y, m.feed) == (10, 5, 800)
    assert m.comment == "cut"


def test_move_from_line_arc():
    a = move_from_line(parse_line("G3 X10 Y10 I5 J0 F400"))
    assert isinstance(a, ArcMove)
    assert a.type is MoveType.ARC_CCW
    assert (a.i, a.j) == (5, 0)


def test_move_from_line_non_motion_is_none():
    assert move_from_line(parse_line("M3 S12000")) is None
    assert move_from_line(parse_line("; comment")) is None


def test_parse_moves_skips_non_motion():
    text = "G21\nM3 S1000\nG1 X10 F100\nG0 Z5\nM30\n"
    moves = parse_moves(text)
    assert [m.type for m in moves] == [MoveType.LINEAR, MoveType.RAPID]


def test_parse_program_model_infers_header_footer():
    text = "G20\nG91\nG28\nG1 X10 F100\nM2\n"
    prog = parse_program_model(text)
    assert prog.header.units is Units.INCH
    assert prog.header.absolute is False
    assert prog.header.home is True
    assert prog.footer.end_code == "M2"
    assert len(prog.moves) == 1
