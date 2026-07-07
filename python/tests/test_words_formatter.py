from cam_creation_studio.gcode.formatter import comment_line, format_line, render, section_line
from cam_creation_studio.gcode.words import Line, Word


# ---- Word -> Line -> String ----
def test_word_render():
    assert Word("X", 10.5).render() == "X10.5"
    assert Word("F", 1200).render() == "F1200"
    assert Word("S", 18000).render() == "S18000"
    assert Word("Z", 10.0).render() == "Z10"  # trailing .0 dropped


def test_line_render_full():
    line = Line("G1", [Word("X", 10), Word("Y", 5), Word("F", 800)], "cut move")
    assert line.render() == "G1 X10 Y5 F800 ; cut move"


def test_line_of_skips_empty_and_none():
    line = Line.of("G1", {"X": 10, "Y": "", "Z": None, "F": 800})
    assert line.render() == "G1 X10 F800"


def test_bare_comment_line():
    assert Line(comment="note").render() == "; note"
    assert render(Line(comment="--- HEADER ---")) == section_line("HEADER")


def test_format_line_adapter_matches_line():
    assert format_line("G1", {"X": 10, "Y": 5, "F": 800}, "cut move") == \
        render(Line.of("G1", {"X": 10, "Y": 5, "F": 800}, "cut move"))


def test_comment_and_section_helpers():
    assert comment_line("hi") == "; hi"
    assert section_line("BODY") == "; --- BODY ---"
