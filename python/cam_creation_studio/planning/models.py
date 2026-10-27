"""Typed inputs and results for the rectangular centerline planner.

The result stores a CS-016 ``ToolpathPlan``. It does not keep a second
motion array.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..toolpath.models import ToolpathPlan


@dataclass(frozen=True, slots=True)
class RectangularPlannerOptions:
    """Explicit selections. Stored feed advice is not an input."""

    planned_cut_feed_mm_min: float
    planned_plunge_feed_mm_min: float
    recommendation_id: str | None
    depth_levels_mm: tuple[float, ...]
    travel_height_mm: float
    clearance_mm: float
    stepdown_mm: float
    removal_max_depth_mm: float
    stock_allowance_mm: float


@dataclass(frozen=True, slots=True)
class NormalizedRectangle:
    """Start corner ``(x_min, y_min)`` and the four boundary edge ids.

    Edge ids follow the deterministic traversal, not the selection order.
    """

    x_min_mm: float
    y_min_mm: float
    x_max_mm: float
    y_max_mm: float
    edge_ids: tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class RectangularExpansion:
    """One validated canonical plan for a normalized rectangle."""

    plan: ToolpathPlan
    rectangle: NormalizedRectangle
