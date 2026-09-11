"""Canonical controller-neutral motion contracts (CS-016).

These dataclasses are the production form of the CS-015 Candidate B
architecture. They store planned cutter-center motion, not preview segments
and not G-code instructions.

Units are millimetres. Poses are explicit: axes are never omitted for
modality. See ``docs/architecture/TOOLPATH_CONTRACT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..shared.geometry import Point
from .enums import MotionKind

TOOLPATH_PLAN_V1 = "camstudio_toolpath_v1"
TOOLPATH_PLAN_VERSION = TOOLPATH_PLAN_V1


@dataclass(frozen=True, slots=True)
class ToolpathStrategy:
    """Descriptive planning inputs. Does not generate geometry.

    ``label`` is presentation-only and is excluded from fingerprints.
    ``travel_height_mm`` is a planned Z, not a safety rating.
    Depth levels, offsets, and pecks are stored when supplied; this object
    does not compute them.
    """

    travel_height_mm: float
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    peck_depth_mm: float | None = None
    retract_height_mm: float | None = None
    label: str = ""


@dataclass(frozen=True, slots=True)
class LinearMotion:
    """Explicit pose-to-pose linear motion."""

    id: str
    kind: MotionKind
    start: Point
    end: Point
    planned_feed_mm_min: float | None = None
    geometry_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, MotionKind):
            object.__setattr__(self, "kind", MotionKind(self.kind))


@dataclass(frozen=True, slots=True)
class ArcMotion:
    """Analytic circular motion in XY. Tessellation is a view, not storage.

    ``clockwise`` true ⇒ ``sweep_rad`` ≤ 0; false ⇒ ``sweep_rad`` ≥ 0.
    Coincident start/end with |sweep| = 2π is a full turn, not a zero-length
    arc. ``center`` is absolute millimetres, not a G-code I/J offset.
    """

    id: str
    kind: MotionKind
    start: Point
    end: Point
    center: Point
    radius: float
    clockwise: bool
    sweep_rad: float
    planned_feed_mm_min: float | None = None
    geometry_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, MotionKind):
            object.__setattr__(self, "kind", MotionKind(self.kind))


MotionSegment = LinearMotion | ArcMotion


@dataclass(frozen=True, slots=True)
class OperationPath:
    """Ordered motions for one generated pass or approach.

    Order is semantically meaningful and is not sorted on serialization.
    ``depth_mm`` is a pass magnitude when the path is a depth level; it is
    not ``target_depth_mm``.
    """

    id: str
    motions: tuple[MotionSegment, ...]
    depth_mm: float | None = None


@dataclass(frozen=True, slots=True)
class ToolpathPlan:
    """Versioned sibling document of planned cutter-center motion.

    Not stored inside an ``OperationPlan``. ``recommendation_id`` is
    provenance to advisory CS-014 advice; ``planned_feed_mm_min`` is the
    value selected for this path. Neither is execution authority.
    Empty per-motion ``geometry_ids`` inherit the plan-level tuple.
    """

    id: str
    version: str
    operation_definition_id: str
    geometry_ids: tuple[str, ...]
    binding_id: str
    strategy_fingerprint: str
    upstream_fingerprint: str
    paths: tuple[OperationPath, ...]
    recommendation_id: str | None = None
    planned_feed_mm_min: float | None = None
