"""Canonical manufacturing operation-definition contracts (CS-012).

Each definition records what machining operation the user intends and the
geometry-relative parameters required to describe it. It does not record
how the cutter will travel, which tool or material to use, or feeds/speeds.

Definitions reference a CS-011 :class:`OperationIntent` by ``intent_id``.
They do not copy selection IDs, geometry IDs, or operation kind: the intent
remains the ownership link.

Dimensional fields are millimetre magnitudes. Depth is a positive planning
distance, not a signed machine Z coordinate. Optional parameters use
``None`` for unspecified — never a magic zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import ContourRelation, CutDirection, SlotRelation


@dataclass(frozen=True, slots=True)
class ContourDefinition:
    """Planning parameters for a contour intent.

    ``relation`` is declarative. No offset or cutter compensation is
    computed from it. ``direction`` is preference only.
    """

    id: str
    intent_id: str
    target_depth_mm: float
    relation: ContourRelation = ContourRelation.ON
    direction: CutDirection = CutDirection.UNSPECIFIED
    stock_allowance_mm: float | None = None


@dataclass(frozen=True, slots=True)
class PocketDefinition:
    """Planning parameters for a pocket intent.

    Allowances are user-entered material left for a later finishing
    operation. No stepover, island recognition, or clearing algorithm.
    """

    id: str
    intent_id: str
    target_depth_mm: float
    direction: CutDirection = CutDirection.UNSPECIFIED
    wall_allowance_mm: float | None = None
    floor_allowance_mm: float | None = None


@dataclass(frozen=True, slots=True)
class DrillDefinition:
    """Planning parameters for a drill intent.

    ``peck_depth_mm`` and ``retract_height_mm`` are planning intent only.
    No canned-cycle generation.
    """

    id: str
    intent_id: str
    target_depth_mm: float
    retract_height_mm: float | None = None
    peck_depth_mm: float | None = None


@dataclass(frozen=True, slots=True)
class EngraveDefinition:
    """Planning parameters for an engrave intent.

    v1 is intentionally small: identity, intent, and target depth.
    """

    id: str
    intent_id: str
    target_depth_mm: float


@dataclass(frozen=True, slots=True)
class SlotDefinition:
    """Planning parameters for a slot intent.

    ``slot_width_mm`` is intended finished width, not cutter diameter.
    ``relation`` is declarative; v1 only permits on-path.
    """

    id: str
    intent_id: str
    target_depth_mm: float
    slot_width_mm: float | None = None
    direction: CutDirection = CutDirection.UNSPECIFIED
    relation: SlotRelation = SlotRelation.ON_PATH


@dataclass(frozen=True, slots=True)
class ReferenceDefinition:
    """A non-machining designation.

    ``REFERENCE`` carries no depth, allowance, direction, width, or peck
    settings. It remains a deliberate placeholder.
    """

    id: str
    intent_id: str


OperationDefinition = (
    ContourDefinition
    | PocketDefinition
    | DrillDefinition
    | EngraveDefinition
    | SlotDefinition
    | ReferenceDefinition
)

_TYPE_NAME = {
    ContourDefinition: "contour",
    PocketDefinition: "pocket",
    DrillDefinition: "drill",
    EngraveDefinition: "engrave",
    SlotDefinition: "slot",
    ReferenceDefinition: "reference",
}


def definition_type_name(definition: OperationDefinition) -> str:
    """Wire discriminator for ``definition`` (``contour``, ``pocket``, …)."""
    try:
        return _TYPE_NAME[type(definition)]
    except KeyError as exc:
        raise TypeError(
            f"unknown operation-definition type {type(definition)!r}"
        ) from exc
