"""Human/JSON-friendly summary of an imported collection (CS-008).

A summary is a deterministic snapshot for inspection: how many of each entity
kind, the overall bounds, and the layers present. It carries no machining
interpretation — it answers "what geometry exists", nothing about how to cut it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..shared.geometry import Bounds
from .models import GeometryCollection


@dataclass(frozen=True, slots=True)
class GeometrySummary:
    """Counts, bounds, and layers for a :class:`GeometryCollection`."""

    lines: int
    arcs: int
    circles: int
    polylines: int
    splines: int
    total: int
    bounds: Optional[Bounds]
    layers: List[str]


def summarize(collection: GeometryCollection) -> GeometrySummary:
    """Produce a deterministic :class:`GeometrySummary` for ``collection``."""
    counts = collection.counts()
    return GeometrySummary(
        lines=counts["line"],
        arcs=counts["arc"],
        circles=counts["circle"],
        polylines=counts["polyline"],
        splines=counts["spline"],
        total=len(collection.entities),
        bounds=collection.bounds,
        layers=collection.layers,
    )
