"""A small, forgiving G-code parser.

Turns G-code text into structured lines so the validator and preview model can
reason about a program. This is a lexical parser — it understands words and
comments, not machine semantics. It does not execute or validate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
