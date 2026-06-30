from cam_creation_studio.gcode.parser import parse_line, parse_program


def test_parses_words_and_comment():
    ln = parse_line("G1 X10 Y5 F800 ; cut move")
    assert ln.word("X") == 10 and ln.word("Y") == 5 and ln.word("F") == 800
    assert ln.comment == "cut move"
    assert ln.motion == "G1"


def test_parses_without_spaces():
    ln = parse_line("G1X10Y-5Z-0.5")
    assert ln.word("X") == 10 and ln.word("Y") == -5 and ln.word("Z") == -0.5


def test_paren_comment():
    ln = parse_line("G0 X0 (rapid home)")
    assert ln.comment == "rapid home"
    assert ln.word("X") == 0


def test_gword_and_mword():
    ln = parse_line("G21")
    assert ln.gword(21) and not ln.gword(20)
    ln2 = parse_line("M3 S12000")
    assert ln2.mword(3) and ln2.word("S") == 12000


def test_arc_detection():
    assert parse_line("G2 X1 Y1 I1 J0").is_arc
    assert not parse_line("G1 X1").is_arc


def test_program_line_numbers():
    prog = parse_program("G21\nG90\nG1 X1 F100\n")
    assert [l.number for l in prog] == [1, 2, 3]
    assert prog[2].motion == "G1"


def test_empty_line():
    assert parse_line("").is_empty
    assert parse_line("   ; only a comment").is_empty is False
