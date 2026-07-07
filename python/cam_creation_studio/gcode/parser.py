"""A small, forgiving G-code parser.

Turns G-code text into structured lines so the validator and preview model can
reason about a program. This is a lexical parser — it understands words and
comments, not machine semantics. It does not execute or validate.

Two levels are available:

* :func:`parse_line` / :func:`parse_program` produce :class:`ParsedLine` objects
  (raw words + comment), the low-level lexical view.
* :func:`parse_moves` / :func:`parse_program_model` lift motion lines into the
  domain model (:class:`Move` / :class:`ArcMove` / :class:`GCodeProgram`), so a
  generated program round-trips back into typed objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..enums import MoveType, Units
from ..models import ArcMove, GCodeProgram, Move, ProgramFooter, ProgramHeader

# One word = a letter followed by a (signed, optional-decimal) number.
_WORD_RE = re.compile(r"([A-Za-z])\s*(-?\d*\.?\d+)")
_MOTION_CODES = ("G0", "G1", "G2", "G3")


@dataclass
class ParsedLine:
    number: int  # 1-based line number
    raw: str
    words: List[Tuple[str, float]] = field(default_factory=list)
    comment: str = ""

    @property
    def codes(self) -> Dict[str, float]:
        """Mapping of letter -> value (last occurrence wins)."""
        return {letter: value for letter, value in self.words}

    @property
    def is_empty(self) -> bool:
        return not self.words and not self.comment

    def word(self, letter: str) -> Optional[float]:
        for ltr, value in self.words:
            if ltr.upper() == letter.upper():
                return value
        return None

    def has(self, letter: str) -> bool:
        return self.word(letter) is not None

    def gword(self, value: int) -> bool:
        """True if this line contains G<value> (e.g. gword(21) for G21)."""
        for ltr, val in self.words:
            if ltr.upper() == "G" and int(val) == value:
                return True
        return False

    def mword(self, value: int) -> bool:
        """True if this line contains M<value> (e.g. mword(3) for M3)."""
        for ltr, val in self.words:
            if ltr.upper() == "M" and int(val) == value:
                return True
        return False

    @property
    def motion(self) -> Optional[str]:
        """The motion command on this line ('G0'..'G3'), or None."""
        for ltr, val in self.words:
            if ltr.upper() == "G":
                code = f"G{int(val)}"
                if code in _MOTION_CODES:
                    return code
        return None

    @property
    def is_arc(self) -> bool:
        return self.motion in ("G2", "G3")


def parse_line(text: str, number: int = 1) -> ParsedLine:
    """Parse a single line of G-code into a ParsedLine.

    Comment styles: ';' to end of line, and '(' ... ')' inline comments.
    """
    raw = text.rstrip("\n")
    code_part = raw
    comment = ""

    # ';' comment runs to end of line.
    semi = code_part.find(";")
    if semi != -1:
        comment = code_part[semi + 1:].strip()
        code_part = code_part[:semi]

    # '(' ... ')' inline comment(s): capture the first, strip all from the code.
    paren = re.search(r"\(([^)]*)\)", code_part)
    if paren and not comment:
        comment = paren.group(1).strip()
    code_part = re.sub(r"\([^)]*\)", " ", code_part)

    words = [(ltr.upper(), float(num)) for ltr, num in _WORD_RE.findall(code_part)]
    return ParsedLine(number=number, raw=raw, words=words, comment=comment)


def parse_program(text: str) -> List[ParsedLine]:
    """Parse a full G-code program into a list of ParsedLine (1-based numbers)."""
    lines = []
    for i, raw in enumerate(text.splitlines(), start=1):
        lines.append(parse_line(raw, i))
    return lines


# --------------------------------------------------------------------------- #
# Domain-model parsing: ParsedLine -> Move / ArcMove / GCodeProgram
# --------------------------------------------------------------------------- #
def move_from_line(line: ParsedLine):
    """Lift a single :class:`ParsedLine` into a Move/ArcMove, or ``None``.

    Returns ``None`` for non-motion lines. Feed is taken from the line itself (no
    modal carry-over), which is what round-tripping generated output expects.
    """
    motion = line.motion
    if motion is None:
        return None
    mtype = MoveType(motion)
    feed = line.word("F")
    if mtype.is_arc:
        return ArcMove(
            type=mtype,
            x=line.word("X"), y=line.word("Y"), z=line.word("Z"),
            i=line.word("I"), j=line.word("J"), r=line.word("R"),
            feed=feed, comment=line.comment,
        )
    return Move(
        type=mtype,
        x=line.word("X"), y=line.word("Y"), z=line.word("Z"),
        feed=feed, e=line.word("E"), comment=line.comment,
    )


def parse_moves(text: str) -> List:
    """Parse a program's motion lines into a list of Move/ArcMove."""
    moves = []
    for line in parse_program(text):
        m = move_from_line(line)
        if m is not None:
            moves.append(m)
    return moves


def _infer_header(lines: List[ParsedLine]) -> ProgramHeader:
    units = Units.MM
    absolute = True
    home = False
    for ln in lines:
        if ln.gword(20):
            units = Units.INCH
        elif ln.gword(21):
            units = Units.MM
        if ln.gword(90):
            absolute = True
        elif ln.gword(91):
            absolute = False
        if ln.gword(28):
            home = True
    return ProgramHeader(units=units, absolute=absolute, home=home)


def _infer_footer(lines: List[ParsedLine]) -> ProgramFooter:
    units = Units.MM
    end_code = "M30"
    for ln in lines:
        if ln.gword(20):
            units = Units.INCH
        elif ln.gword(21):
            units = Units.MM
        if ln.mword(2):
            end_code = "M2"
        elif ln.mword(30):
            end_code = "M30"
    return ProgramFooter(units=units, end_code=end_code)


def parse_program_model(text: str) -> GCodeProgram:
    """Parse G-code text into a typed :class:`GCodeProgram`.

    Motion lines become Move/ArcMove; units, positioning, home, and the end code
    are inferred where the text declares them. Machine dialect is not encoded in
    plain G-code, so it is left at the model default — round-trip fidelity is at
    the move level.
    """
    lines = parse_program(text)
    moves = [m for m in (move_from_line(ln) for ln in lines) if m is not None]
    return GCodeProgram(
        header=_infer_header(lines),
        moves=moves,
        footer=_infer_footer(lines),
    )
