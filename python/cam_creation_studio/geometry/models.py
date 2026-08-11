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

from ..enums import DiagnosticSeverity
from ..shared.geometry import Bounds, Point
from ..shared.serialization import from_dict as _generic_from_dict
from ..shared.serialization import to_dict as _generic_to_dict
from . import bounds as _bounds
from .diagnostics import GeometryDiagnostic


# --------------------------------------------------------------------------- #
# Entities. All immutable; all reuse shared Point for coordinates.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SourceReference:
    """Where an imported entity came from in the source DXF (CS-008R F6).

    Evidence, not interpretation: it says nothing about how the geometry should
    be machined, only how to find it again in the file it came from.

    ``ordinal`` is the entity's **position in the modelspace**, not its index in
    :attr:`GeometryCollection.entities`. The two differ whenever something was
    dropped, and that difference is the point — ordinals 0, 1, 3 record that the
    second modelspace entity did not survive. Collection position is already
    available from list order, so the explicit field is spent on the fact that
    order alone cannot express.

    Every field is optional except the DXF type, because a source may legitimately
    withhold one: a handle can be absent and a layer unreadable. An absent value
    is recorded as ``None`` rather than invented.
    """

    entity_type: str
    handle: Optional[str] = None
    layer: Optional[str] = None
    ordinal: Optional[int] = None


# Provenance is attached to every entity below as::
#
#     source: Optional[SourceReference] = field(default=None, compare=False)
#
# ``compare=False`` is deliberate. Geometry equality stays *geometric*: two
# identical shapes compare equal whether or not they came from the same DXF
# handle. Provenance is still serialized, still immutable, and still inspectable
# through ``.source`` — it simply does not redefine what it means for two pieces
# of geometry to be the same. Including it would make every imported entity
# unequal to every other and quietly break any future geometric comparison.


@dataclass(frozen=True, slots=True)
class Line2D:
    """A straight segment from ``start`` to ``end`` (mm)."""

    start: Point
    end: Point
    layer: str = "0"
    kind: str = "line"
    source: Optional[SourceReference] = field(default=None, compare=False)

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
    source: Optional[SourceReference] = field(default=None, compare=False)

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
    source: Optional[SourceReference] = field(default=None, compare=False)

    @property
    def bounds(self) -> Bounds:
        cx, cy, r = self.center.x, self.center.y, self.radius
        return Bounds(cx - r, cy - r, cx + r, cy + r)


@dataclass(frozen=True, slots=True)
class Polyline2D:
    """An open or closed chain of vertices (mm).

    Represents an ordered vertex chain and **does not itself guarantee XY
    planarity**; vertices may carry non-zero z. A consumer that requires an
    XY-planar profile must establish that invariant explicitly rather than assume
    it from the type. Which diagnostic a particular importer raises for non-planar
    input is that importer's concern, not part of this model's contract.
    """

    vertices: List[Point]
    closed: bool = False
    layer: str = "0"
    kind: str = "polyline"
    source: Optional[SourceReference] = field(default=None, compare=False)

    @property
    def bounds(self) -> Optional[Bounds]:
        return _bounds.bounds_of_points(self.vertices)


# How a spline's geometry is given. DXF allows either; they are not
# interchangeable, and converting between them is curve mathematics this layer
# deliberately does not perform.
REPRESENTATION_CONTROL = "control"   # control points define the curve
REPRESENTATION_FIT = "fit"           # the curve passes through fit points


@dataclass(frozen=True, slots=True)
class Spline2D:
    """A spline, preserved as the source defined it (mm).

    DXF gives a spline one of two ways, and this model keeps whichever it was
    handed rather than converting: ``representation`` says which, and the
    matching point list is authoritative. Deriving control points from fit points
    is curve fitting — real spline mathematics — and belongs nowhere near an
    importer whose job is to preserve evidence.

    ``knots`` and ``weights`` are **not** scaled with the drawing units. Knots
    live in parameter space and weights are dimensionless; multiplying either by
    a mm conversion would corrupt the curve.

    Invariant: a spline must carry the points its declared representation needs.
    A spline with neither control nor fit points is not a degenerate entity to be
    kept with a warning — it is not geometry at all, and the importer excludes it
    rather than admitting an entity that counts as imported while containing
    nothing.
    """

    control_points: List[Point] = field(default_factory=list)
    fit_points: List[Point] = field(default_factory=list)
    knots: List[float] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)
    degree: int = 3
    closed: bool = False
    periodic: bool = False
    rational: bool = False
    representation: str = REPRESENTATION_CONTROL
    layer: str = "0"
    kind: str = "spline"
    source: Optional[SourceReference] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.representation not in (REPRESENTATION_CONTROL, REPRESENTATION_FIT):
            raise ValueError(
                f"Spline2D.representation must be "
                f"{REPRESENTATION_CONTROL!r} or {REPRESENTATION_FIT!r}, "
                f"got {self.representation!r}")
        if not self.defining_points:
            raise ValueError(
                f"Spline2D declares representation={self.representation!r} but "
                f"carries no {self.representation} points; an empty spline is not "
                "valid geometry.")

    @property
    def defining_points(self) -> List[Point]:
        """The point list that actually defines this curve."""
        if self.representation == REPRESENTATION_FIT:
            return self.fit_points
        return self.control_points

    @property
    def bounds(self) -> Optional[Bounds]:
        """Box over the defining points.

        For a control-point spline this is the control hull — a superset of the
        curve, so safe to reason about.

        For a **fit-point** spline it is **not conservative**. The curve
        interpolates the fit points and overshoots between them, so the box can
        be smaller than the curve. Measured against sampled curves, ordinary
        shapes exceed it by a visible margin:

        ============================================  ==================
        fit points                                    curve exceeds box
        ============================================  ==================
        ``(0,0) (5,8) (10,0)``                        0.00 mm
        ``(0,0) (4,10) (6,10) (10,0)``                0.10 mm
        ``(0,0) (2,10) (4,0) (6,10) (8,0)``           0.22 mm
        ``(0,0) (1,9) (9,9) (10,0)``                  1.13 mm
        ============================================  ==================

        So a caller must not use these bounds for anything where a too-small box
        is unsafe — culling, clipping, containment, or a machining envelope
        check. Tightening them means evaluating the curve, which is spline
        mathematics and does not belong in an importer. Use
        :attr:`representation` to tell the two cases apart.
        """
        return _bounds.bounds_of_points(self.defining_points)


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
    """Provenance for an imported collection. Source evidence, not interpretation.

    ``entity_count`` is the number of entities *preserved as geometry* — not the
    number in the file. ``raw_entity_count`` is what the modelspace actually held,
    and ``unsupported_entity_count`` is how many were dropped as unsupported. Use
    :attr:`has_lossy_import` to tell at a glance whether a "successful" import
    silently omitted geometry, rather than having to scan the diagnostics.
    """

    source_path: str
    source_units: str          # original unit name ("in", "mm", "unknown", ...)
    unit_scale: float          # factor applied to reach millimetres
    dxf_version: Optional[str] = None
    entity_count: int = 0                # entities preserved as geometry
    raw_entity_count: int = 0            # entities present in the DXF modelspace
    unsupported_entity_count: int = 0    # entities dropped as unsupported

    @property
    def has_lossy_import(self) -> bool:
        """True when one or more source entities produced no geometry at all."""
        return self.unsupported_entity_count > 0


@dataclass(frozen=True, slots=True)
class ImportReport:
    """A flat summary of one import, derived from a :class:`GeometryCollection`.

    Purely a *view*: every number here is computed from entities, metadata, and
    diagnostics that already exist. It introduces no new finding type and is
    never a source of truth — :meth:`GeometryCollection.report` rebuilds it on
    demand, so it cannot drift from the collection it describes.

    There is no duration field. Wall-clock time would make two imports of the
    same file compare unequal and destabilize fixtures, for a number that says
    nothing about fidelity.

    ``entity_count`` is counted from the **live collection**, not copied from
    :attr:`ImportMetadata.entity_count`. The two normally agree; where they do
    not, the collection is right and the metadata is a stale record of what some
    earlier import believed. A view that reported the recorded number would be
    describing history rather than the object in hand. The other counts —
    ``raw_entity_count`` and ``unsupported_entity_count`` — have no live
    equivalent to recount, so they *are* taken from metadata.

    ``counts_by_kind`` and ``counts_by_severity`` both carry every possible key,
    zeros included, so a consumer can index either without guarding for absence.
    """

    source_path: Optional[str] = None
    source_units: Optional[str] = None
    unit_scale: Optional[float] = None
    dxf_version: Optional[str] = None

    raw_entity_count: int = 0
    entity_count: int = 0
    unsupported_entity_count: int = 0
    counts_by_kind: dict = field(default_factory=dict)

    diagnostic_count: int = 0
    counts_by_severity: dict = field(default_factory=dict)
    codes: List[str] = field(default_factory=list)

    loss_count: int = 0
    recoverable_loss_count: int = 0
    unrecoverable_loss_count: int = 0

    bounds: Optional[Bounds] = None

    @property
    def has_loss(self) -> bool:
        """True when any source information failed to survive the import."""
        return self.loss_count > 0

    @property
    def has_unrecoverable_loss(self) -> bool:
        """True when something was lost that no surviving evidence can rebuild."""
        return self.unrecoverable_loss_count > 0

    def as_dict(self) -> dict:
        return _generic_to_dict(self)


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

    @property
    def losses(self) -> List[GeometryDiagnostic]:
        """Diagnostics recording information that did not survive, in order."""
        return [d for d in self.diagnostics if d.is_loss]

    def report(self) -> "ImportReport":
        """Summarize this import. Recomputed each call, so it cannot go stale."""
        meta = self.metadata
        # Seeded with every severity, mirroring counts() over kinds, so both count
        # maps in the report have the same shape and neither needs a .get() guard.
        severities: dict = {s.value: 0 for s in DiagnosticSeverity}
        for d in self.diagnostics:
            severities[d.severity.value] += 1

        losses = self.losses
        return ImportReport(
            source_path=meta.source_path if meta else None,
            source_units=meta.source_units if meta else None,
            unit_scale=meta.unit_scale if meta else None,
            dxf_version=meta.dxf_version if meta else None,
            raw_entity_count=meta.raw_entity_count if meta else 0,
            entity_count=len(self.entities),
            unsupported_entity_count=meta.unsupported_entity_count if meta else 0,
            counts_by_kind=self.counts(),
            diagnostic_count=len(self.diagnostics),
            counts_by_severity=severities,
            codes=sorted({d.code for d in self.diagnostics}),
            loss_count=len(losses),
            recoverable_loss_count=sum(1 for d in losses if d.recoverable is True),
            unrecoverable_loss_count=sum(1 for d in losses if d.recoverable is False),
            bounds=self.bounds,
        )

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
    "REPRESENTATION_CONTROL",
    "REPRESENTATION_FIT",
    "Entity",
    "ImportMetadata",
    "ImportReport",
    "GeometryCollection",
]
