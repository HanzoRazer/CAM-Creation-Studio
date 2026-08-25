"""Closed manufacturing-planning vocabularies (CS-012).

These record user preference only. They do not compute offsets, winding
direction, or toolpath geometry. Unknown serialized values must fail at
reconstruction rather than be silently admitted.
"""

from __future__ import annotations

from enum import Enum


class ContourRelation(str, Enum):
    """Where a contour is intended relative to selected geometry.

    Declarative only — no cutter-compensation or offset is produced.
    """

    ON = "on"
    INSIDE = "inside"
    OUTSIDE = "outside"


class CutDirection(str, Enum):
    """Preferred milling direction. Preference, not a toolpath guarantee."""

    CLIMB = "climb"
    CONVENTIONAL = "conventional"
    UNSPECIFIED = "unspecified"


class SlotRelation(str, Enum):
    """Where a slot is intended relative to selected geometry.

    v1 has a single legal value so the relationship is explicit and future
    members have a legitimate place to land. Unknown values still fail closed.
    """

    ON_PATH = "on_path"
