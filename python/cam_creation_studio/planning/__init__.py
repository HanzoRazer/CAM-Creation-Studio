"""Bounded planning algorithms.

``toolpath`` remains the motion contract. This package expands an explicit
rectangular cutter centerline into that contract. It does not offset
contours, and ``toolpath`` does not import it.
"""

from __future__ import annotations

from .errors import PlanningError
from .limits import (
    GENERATED_MANIFEST_VERSION,
    GENERATED_PLAN_VERSION,
    INPUT_VERSION,
    MAX_DEPTH_LEVELS,
    MAX_MOTIONS,
    MAX_PLANNER_INPUT_BYTES,
    MOTION_SOURCE,
    PLANNER_ID,
    PLANNER_VERSION,
)
from .models import (
    NormalizedRectangle,
    RectangularExpansion,
    RectangularPlannerOptions,
)
from .rectangular import expand_rectangular_contour, normalize_rectangle

__all__ = [
    "GENERATED_MANIFEST_VERSION",
    "GENERATED_PLAN_VERSION",
    "INPUT_VERSION",
    "MAX_DEPTH_LEVELS",
    "MAX_MOTIONS",
    "MAX_PLANNER_INPUT_BYTES",
    "MOTION_SOURCE",
    "PLANNER_ID",
    "PLANNER_VERSION",
    "NormalizedRectangle",
    "PlanningError",
    "RectangularExpansion",
    "RectangularPlannerOptions",
    "expand_rectangular_contour",
    "normalize_rectangle",
]
