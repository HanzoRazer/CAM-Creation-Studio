"""Normalize G-code line output.

A G-code line is a command word (G1, M3, ...) followed by parameter "words"
(X10, Y5, F800) and an optional trailing comment. This module is the single
place that decides spacing, number rounding, and comment style.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..shared.numbers import round_for_gcode


def _format_value(value: Any, decimals: int) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(round_for_gcode(value, decimals))
    return str(value)


def format_line(
    command: str,
    words: Optional[Mapping[str, Any]] = None,
    comment: str = "",
    decimals: int = 3,
) -> str:
    """Build a single G-code line.

    >>> format_line("G1", {"X": 10, "Y": 5, "F": 800}, "cut move")
    'G1 X10 Y5 F800 ; cut move'

    Words whose value is ``None`` or ``""`` are skipped. Insertion order is
    preserved.
    """
    parts = []
    if command:
        parts.append(command)
    for letter, value in (words or {}).items():
        if value is None or value == "":
            continue
        parts.append(f"{letter}{_format_value(value, decimals)}")
    line = " ".join(parts)
    if comment:
        line = f"{line} ; {comment}" if line else f"; {comment}"
    return line


def comment_line(text: str) -> str:
    """Emit a standalone comment line: '; text'."""
    return f"; {text}"


def section_line(title: str) -> str:
    """Emit a section banner used throughout generated programs."""
    return f"; --- {title} ---"
