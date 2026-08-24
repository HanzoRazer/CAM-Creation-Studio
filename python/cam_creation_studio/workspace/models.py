"""Canonical geometry-workspace contracts (CS-011).

The workspace is the first authorized application-layer consumer of a
:class:`~cam_creation_studio.geometry.models.GeometryCollection`. It holds
imported geometry as **immutable source evidence** and attaches application
state — selections, groups, operation intent — by reference.

It answers planning questions only: what is loaded, what the user selected,
how they grouped it, and what operation category they currently intend. It
does not answer machining questions (tool, feeds, depth, side, toolpath,
G-code, machine readiness).

Two identity kinds live here and must not be conflated:

* :class:`GeometryRef` IDs are a **deterministic identity of imported
  geometry**, derived from source order and provenance.
* Selection / group / operation IDs are a **deterministic workspace-object
  identity generated from creation context** (kind, name, members, and the
  count of existing objects of that kind). Renaming or reconstructing a
  selection does not automatically preserve its ID.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..geometry.models import GeometryCollection

# Persistence contract. Changes after release must be additive or carry an
# explicit migration. Do not treat dataclass layout as the schema.
WORKSPACE_VERSION = "camstudio_geometry_workspace_v1"


class OperationKind(str, Enum):
    """User-declared operation category. Intent only — not a machining plan.

    ``REFERENCE`` means the selection is in the workspace but is not currently
    designated for machining. There is no ``UNKNOWN`` member: an unknown
    serialized value must fail at reconstruction rather than be silently
    admitted.
    """

    CONTOUR = "contour"
    POCKET = "pocket"
    DRILL = "drill"
    ENGRAVE = "engrave"
    SLOT = "slot"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class GeometryRef:
    """Stable workspace identity for one retained imported entity.

    ``id`` is the application identifier. ``entity_index`` is the entity's
    position in :attr:`GeometryCollection.entities` at workspace construction
    — source order, not DXF handle. One retained entity ↔ one ref.
    """

    id: str
    entity_index: int


@dataclass(frozen=True, slots=True)
class GeometrySelection:
    """An ordered set of workspace geometry IDs.

    Empty selections and duplicate member IDs are structurally invalid.
    Member order is the caller's order.
    """

    id: str
    name: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeometryGroup:
    """A named organizational grouping of workspace geometry IDs.

    Names are user labels, not manufacturing semantics. Empty groups and
    duplicate member IDs are structurally invalid. IDs are unique; names
    need not be.
    """

    id: str
    name: str
    entity_ids: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class OperationIntent:
    """A user-declared operation category attached to a selection.

    This is not a machining operation. It carries no tool, feed, depth,
    compensation, or toolpath fields. Shape suitability is not judged here:
    ``DRILL`` on a line is a valid intent, not a validation failure.
    """

    id: str
    name: str
    kind: OperationKind
    selection_id: str


@dataclass(frozen=True, slots=True)
class GeometryWorkspace:
    """Persistent application state over one imported geometry collection.

    ``geometry`` is the imported evidence and is never mutated. Selections,
    groups, and operations reference it; they do not copy points or provenance.
    """

    version: str
    geometry: GeometryCollection
    geometry_refs: tuple[GeometryRef, ...]
    selections: tuple[GeometrySelection, ...] = ()
    groups: tuple[GeometryGroup, ...] = ()
    operations: tuple[OperationIntent, ...] = ()
