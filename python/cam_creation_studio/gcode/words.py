"""G-code words and lines as objects.

The smallest unit of G-code is a *word*: a letter address plus a number, like
``X10.2``, ``F1200``, or ``S18000``. A *line* is a command word (``G1``, ``M3``)
followed by parameter words and an optional comment.

Modeling these as objects — instead of building strings by concatenation — means
the rules for spacing, number formatting, and comment style live in exactly one
place (the formatter), and every layer that emits G-code speaks the same types.

    Word("X", 10.5)                       -> renders as "X10.5"
    Line("G1", [Word("X", 10)], "cut")    -> renders as "G1 X10 ; cut"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional

from ..shared.numbers import round_for_gcode


@dataclass(frozen=True, slots=True)
class Word:
    """A single G-code word: a letter address and its numeric value."""

    letter: str
    value: Any

    def render(self, decimals: int = 3) -> str:
        return f"{self.letter}{_format_value(self.value, decimals)}"


@dataclass(frozen=True, slots=True)
class Line:
    """A command word, its parameter words, and an optional trailing comment.

    A ``Line`` with no command but a comment renders as a bare comment line.
    """

    command: str = ""
    words: List[Word] = field(default_factory=list)
    comment: str = ""

    @classmethod
    def of(
        cls,
        command: str,
        words: Optional[Mapping[str, Any]] = None,
        comment: str = "",
    ) -> "Line":
        """Build a Line from a ``{letter: value}`` mapping.

        Words whose value is ``None`` or ``""`` are dropped; insertion order is
        preserved. This is the bridge the dict-based adapters use.
        """
        built = [
            Word(letter, value)
            for letter, value in (words or {}).items()
            if value is not None and value != ""
        ]
        return cls(command=command, words=built, comment=comment)

    def render(self, decimals: int = 3) -> str:
        parts: List[str] = []
        if self.command:
            parts.append(self.command)
        parts.extend(w.render(decimals) for w in self.words)
        line = " ".join(parts)
        if self.comment:
            line = f"{line} ; {self.comment}" if line else f"; {self.comment}"
        return line


def _format_value(value: Any, decimals: int) -> str:
    """Render a word's value: numbers rounded (no trailing .0), others as-is."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(round_for_gcode(value, decimals))
    return str(value)
