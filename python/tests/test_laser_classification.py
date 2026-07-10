"""Laser/burn classification for raw G-code text (CS-006).

Raw text carries no machine profile, so ``build_toolpath_model(text)`` must read
cut-vs-burn *intent* from the program itself. The contract:

* a laser/beam/burn marker in a **comment** classifies feed moves as ``burn``;
* an explicit machine context (``laser=`` kwarg, or a typed program's profile)
  always wins over the text heuristic;
* a bare ``M3``/``S`` is NOT laser — that is how a CNC spindle starts too;
* when unsure, classify as ``cut`` (conservative default).

This never infers machine *readiness* — only classification for preview.
"""

from cam_creation_studio.enums import MoveType
from cam_creation_studio.models import GCodeProgram, Move, ProgramHeader
from cam_creation_studio.preview.toolpath_model import (
    BURN,
    CUT,
    build_toolpath_model,
    infer_burn_mode_from_text,
)

# A laser/etch job: a spindle-style ``M3 S`` (which a CNC also emits) PLUS a
# distinctive laser comment. The comment is what tips intent to burn — the
# ``M3 S`` alone must never be enough, and explicit CNC context still overrides.
LASER_TEXT = """\
; laser etch outline
G21
M3 S255
G1 X10 Y0 F600
G1 X10 Y10 F600
"""

# A plain CNC milling program: a spindle start (M3 S...) but no laser markers.
CNC_TEXT = """\
; milling aluminum pocket
G21
M3 S12000
G1 X10 Y0 F800
G1 X10 Y10 F800
"""


def _feed_types(segs):
    """Classification of the material-removing feed moves (cut vs burn)."""
    return {s.type for s in segs if s.type in (CUT, BURN)}


# --- The four required end-to-end cases -------------------------------------

def test_raw_laser_text_is_burn():
    segs = build_toolpath_model(LASER_TEXT)
    assert _feed_types(segs) == {BURN}


def test_explicit_cnc_context_stays_cut():
    # Even with a laser comment AND an M3 S present, explicit CNC context
    # (laser=False) wins and the feed moves stay cut.
    segs = build_toolpath_model(LASER_TEXT, laser=False)
    assert _feed_types(segs) == {CUT}


def test_laser_profile_is_burn():
    prog = GCodeProgram(
        header=ProgramHeader(machine="laser"),
        moves=[Move(type=MoveType.LINEAR, x=10, y=0, feed=600),
               Move(type=MoveType.LINEAR, x=10, y=10, feed=600)],
    )
    segs = build_toolpath_model(prog)
    assert _feed_types(segs) == {BURN}


def test_plain_cnc_text_is_cut():
    segs = build_toolpath_model(CNC_TEXT)
    assert _feed_types(segs) == {CUT}


# --- Direct unit tests for the heuristic ------------------------------------

def test_infer_true_on_comment_marker():
    assert infer_burn_mode_from_text("G1 X10 ; burn edge\n") is True
    assert infer_burn_mode_from_text("(laser pass)\nG1 X10\n") is True
    assert infer_burn_mode_from_text("G1 X10 ; beam on\n") is True


def test_infer_false_on_bare_spindle_start():
    # M3 + S is how a CNC spindle starts — must not be read as laser.
    assert infer_burn_mode_from_text("M3 S12000\nG1 X10 F800\n") is False


def test_infer_false_on_plain_program():
    assert infer_burn_mode_from_text("G21\nG1 X10 Y10 F800\n") is False


def test_marker_in_motion_words_does_not_falsely_trigger():
    # 'laser' only counts inside a comment, never in a code line by itself.
    assert infer_burn_mode_from_text("G1 X10 Y10 F800\n") is False


def test_substring_terms_do_not_false_positive():
    # Whole-word matching: ordinary machining terms that merely *contain* a
    # marker must not be read as laser/burn intent.
    assert infer_burn_mode_from_text("G1 X10 ; burnish finishing pass\n") is False
    assert infer_burn_mode_from_text("(machining oak beams bracket)\nG1 X10\n") is False
    assert infer_burn_mode_from_text("; fixture for laserjet panel\nG1 X10\n") is False


def test_whole_word_marker_with_punctuation_still_triggers():
    # A real marker adjacent to punctuation is still a whole word.
    assert infer_burn_mode_from_text("G1 X10 ; burn-in edge\n") is True
    assert infer_burn_mode_from_text("(laser: outline)\nG1 X10\n") is True
