"""Neutral geometry dataclasses for imported CAD entities (CS-008).

These are the internal, machine-independent representation of 2D geometry. They
carry no machining intent — no cut order, no inside/outside, no operation type —
only *what geometry exists*. Coordinates are always millimetres (the importer
normalizes on the way in) and reuse the canonical
:class:`~cam_creation_studio.shared.geometry.Point` / ``Bounds`` primitives
rather than introducing a parallel 2D point type.

Every entity carries a ``kind`` discriminator string. A :class:`GeometryCollection`
holds entities in a single **source-ordered** list mixing all kinds, so the order
they appeared in the DXF is preserved across types. Because a heterogeneous list
cannot be rebuilt by the reflection-based shared serializer, this module provides
a small custom :meth:`GeometryCollection.from_dict` that dispatches on ``kind``;
serialization *out* still uses the generic ``shared.serialization`` path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Union

from ..shared.geometry import Bounds, Point
from ..shared.serialization import from_dict as _generic_from_dict
from ..shared.serialization import to_dict as _generic_to_dict
from . import bounds as _bounds
from .diagnostics import GeometryDiagnostic


# --------------------------------------------------------------------------- #
# Entities. All immutable; all reuse shared Point for coordinates.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Line2D:
    """A straight segment from ``start`` to ``end`` (mm)."""

    start: Point
    end: Point
    layer: str = "0"
    kind: str = "line"

    @property
    def bounds(self) -> Bounds:
        return _bounds.bounds_of_points([self.start, self.end])


@dataclass(frozen=True, slots=True)
class Arc2D:
    """A circular arc, CCW from ``start_angle`` to ``end_angle`` (degrees, mm)."""

    center: Point
    radius: float
    start_angle: float
    end_angle: float
    layer: str = "0"
    kind: str = "arc"

    @property
    def bounds(self) -> Bounds:
        return _bounds.from_extent(
            _bounds.arc_extent(
                self.center.x, self.center.y, self.radius,
                self.start_angle, self.end_angle,
            )
        )


@dataclass(frozen=True, slots=True)
class Circle2D:
    """A full circle of ``radius`` about ``center`` (mm)."""

    center: Point
    radius: float
    layer: str = "0"
    kind: str = "circle"

    @property
    def bounds(self) -> Bounds:
        cx, cy, r = self.center.x, self.center.y, self.radius
        return Bounds(cx - r, cy - r, cx + r, cy + r)


@dataclass(frozen=True, slots=True)
class Polyline2D:
    """An open or closed chain of vertices (mm)."""

    vertices: List[Point]
    closed: bool = False
    layer: str = "0"
    kind: str = "polyline"

    @property
    def bounds(self) -> Optional[Bounds]:
        return _bounds.bounds_of_points(self.vertices)


@dataclass(frozen=True, slots=True)
class Spline2D:
    """A spline, preserved as its control points + degree (mm).

    We keep the source evidence (control points, degree, closed flag) rather than
    flattening the curve; interpretation and any tessellation happen later.
    """

    control_points: List[Point]
    degree: int = 3
    closed: bool = False
    layer: str = "0"
    kind: str = "spline"

    @property
    def bounds(self) -> Optional[Bounds]:
        # Control-point hull bounds the curve; exact only for interpolating cases,
        # but a deterministic, superset-safe box for preview/inspection.
        return _bounds.bounds_of_points(self.control_points)


Entity = Union[Line2D, Arc2D, Circle2D, Polyline2D, Spline2D]

# Discriminator -> class, for rebuilding a heterogeneous entity list.
_KIND_TO_CLASS = {
    "line": Line2D,
    "arc": Arc2D,
    "circle": Circle2D,
    "polyline": Polyline2D,
    "spline": Spline2D,
}


@dataclass(frozen=True, slots=True)
class ImportMetadata:
    """Provenance for an imported collection. Source evidence, not interpretation."""

    source_path: str
    source_units: str          # original unit name ("in", "mm", "unknown", ...)
    unit_scale: float          # factor applied to reach millimetres
    dxf_version: Optional[str] = None
    entity_count: int = 0


@dataclass(frozen=True, slots=True)
class GeometryCollection:
    """An ordered, heterogeneous set of imported entities plus import evidence.

    ``entities`` preserves the source order across all kinds. ``diagnostics``
    records every advisory finding raised during import — nothing is discarded
    silently.
    """

    entities: List[Entity] = field(default_factory=list)
    metadata: Optional[ImportMetadata] = None
    diagnostics: List[GeometryDiagnostic] = field(default_factory=list)

    # -- derived, deterministic views -------------------------------------- #
    @property
    def bounds(self) -> Optional[Bounds]:
        """Union of every entity's bounds, or ``None`` for an empty collection."""
        return _bounds.union(e.bounds for e in self.entities)

    @property
    def layers(self) -> List[str]:
        """Sorted, de-duplicated layer names present in the collection."""
        return sorted({e.layer for e in self.entities})

    def of_kind(self, kind: str) -> List[Entity]:
        """Entities whose discriminator equals ``kind``, in source order."""
        return [e for e in self.entities if e.kind == kind]

    def counts(self) -> dict:
        """Count of entities per kind (all five kinds always present)."""
        result = {k: 0 for k in _KIND_TO_CLASS}
        for e in self.entities:
            result[e.kind] = result.get(e.kind, 0) + 1
        return result

    # -- serialization ------------------------------------------------------ #
    def to_dict(self) -> dict:
        """JSON-ready dict via the shared generic serializer (out path)."""
        return _generic_to_dict(self)

    def to_json(self, *, indent: Optional[int] = None, sort_keys: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=sort_keys)

    @classmethod
    def from_dict(cls, data: dict) -> "GeometryCollection":
        """Rebuild a collection, dispatching each entity on its ``kind``.

        The reflection serializer cannot reconstruct a heterogeneous list, so we
        route each entity dict to its concrete class here, then defer to the
        generic ``from_dict`` for the (homogeneous) fields of each entity,
        metadata, and diagnostics.
        """
        entities: List[Entity] = []
        for raw in data.get("entities", []):
            kind = raw.get("kind")
            klass = _KIND_TO_CLASS.get(kind)
            if klass is None:
                raise ValueError(f"GeometryCollection.from_dict: unknown entity kind {kind!r}")
            entities.append(_generic_from_dict(klass, raw))

        meta_raw = data.get("metadata")
        metadata = _generic_from_dict(ImportMetadata, meta_raw) if meta_raw else None

        diagnostics = [
            _generic_from_dict(GeometryDiagnostic, d) for d in data.get("diagnostics", [])
        ]
        return cls(entities=entities, metadata=metadata, diagnostics=diagnostics)

    @classmethod
    def from_json(cls, text: str) -> "GeometryCollection":
        return cls.from_dict(json.loads(text))


__all__ = [
    "Line2D",
    "Arc2D",
    "Circle2D",
    "Polyline2D",
    "Spline2D",
    "Entity",
    "ImportMetadata",
    "GeometryCollection",
]
