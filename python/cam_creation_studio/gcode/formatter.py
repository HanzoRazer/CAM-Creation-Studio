"""Normalize G-code line output.

A G-code line is a command word (G1, M3, ...) followed by parameter "words"
(X10, Y5, F800) and an optional trailing comment. This module is the single
place that decides spacing, number rounding, and comment style.

The canonical unit is :class:`~cam_creation_studio.gcode.words.Line`; everything
funnels through :func:`render`. The older ``format_line(command, words, comment)``
signature is kept as a thin dict adapter so existing callers keep working —
under the hood it just builds a ``Line`` and renders it.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .words import Line, Word

__all__ = ["render", "format_line", "comment_line", "section_line", "Line", "Word"]


def render(line: Line, decimals: int = 3) -> str:
    """Render a :class:`Line` to its canonical text form."""
    return line.render(decimals)


def format_line(
    command: str,
    words: Optional[Mapping[str, Any]] = None,
    comment: str = "",
    decimals: int = 3,
) -> str:
    """Build a single G-code line from a ``{letter: value}`` mapping (adapter).

    >>> format_line("G1", {"X": 10, "Y": 5, "F": 800}, "cut move")
    'G1 X10 Y5 F800 ; cut move'

    Words whose value is ``None`` or ``""`` are skipped. Insertion order is
    preserved.
    """
    return render(Line.of(command, words, comment), decimals)


def comment_line(text: str) -> str:
    """Emit a standalone comment line: '; text'."""
    return f"; {text}"


def section_line(title: str) -> str:
    """Emit a section banner used throughout generated programs."""
    return f"; --- {title} ---"
