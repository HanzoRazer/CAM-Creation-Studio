"""Closed vocabularies for controller-neutral planned motion (CS-016).

These are planning semantics, not G-code words and not preview/laser kinds.
Unknown serialized values must fail at reconstruction.
"""

from __future__ import annotations

from enum import Enum


class MotionKind(str, Enum):
    """How a motion relates to the work. Not a G-word."""

    TRAVEL = "travel"
    CUT = "cut"
    PLUNGE = "plunge"
    RETRACT = "retract"


class ToolpathStatus(str, Enum):
    """Structural description of a stored toolpath versus current inputs.

    Informational only. ``STALE`` means fingerprints no longer match. It is
    not a claim that the path is unsafe or machine-ready.
    """

    MISSING = "missing"
    CURRENT = "current"
    STALE = "stale"
