"""CS-015 study-only probe for a controller-neutral toolpath contract.

This module is experimental evidence. It is not a production API.

Production packages under ``cam_creation_studio`` must not import this file.
The probe may import existing preview types **only** to project canonical
study motion into today's view model:

```text
StudyToolpathPlan
     ├── LinearMotion
     └── ArcMotion
             │
             ▼
      preview adapter
             │
             ▼
     ToolpathSegment
```

It does not store ``ToolpathSegment``, ``Move``, or ``ArcMove``. Serialized
study motion must contain no G-code or preview vocabulary.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

_PYTHON = Path(__file__).resolve().parents[2] / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from cam_creation_studio.preview import toolpath_model as preview
from cam_creation_studio.shared.geometry import Point, arc_length, distance
from cam_creation_studio.shared.ids import stable_id

STUDY_VERSION = "camstudio_toolpath_study_v0"

# Tokens that must never appear in canonical serialization (keys or values).
FORBIDDEN_SERIAL_TOKENS = (
    "source_command",
    "G0",
    "G1",
    "G2",
    "G3",
    "M3",
    "M5",
    "MoveType",
    "ToolpathSegment",
    "ArcMove",
    "dialect",
    "controller",
    "postprocessor",
    "machine_ready",
    "approved",
)

# Standalone "Move" is checked as a JSON key/type discriminator, not as a
# substring of "motion". "safe" is avoided in field names (travel height is
# not a machine-safety claim).


class MotionKind(str, Enum):
    """Controller-neutral motion kind. Not a G-word."""

    TRAVEL = "travel"
    CUT = "cut"
    PLUNGE = "plunge"
    RETRACT = "retract"


class CompensationOwner(str, Enum):
    """Where cutter-center geometry is resolved. Study ruling."""

    PLANNER_EXPLICIT = "planner_explicit_cutter_center"


class DrillExpansion(str, Enum):
    """How drilling is represented. No canned-cycle vocabulary."""

    EXPANDED_MOTIONS = "expanded_neutral_motions"


@dataclass(frozen=True, slots=True)
class StudyToolpathStrategy:
    """Planning knobs that generate motion. Not copied onto every segment.

    ``label`` is presentation-only and must not enter the fingerprint.
    ``travel_height_mm`` is a planned Z for travel; it is not a safety rating.
    """

    travel_height_mm: float = 5.0
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    peck_depth_mm: float | None = None
    retract_height_mm: float | None = None
    compensation: CompensationOwner = CompensationOwner.PLANNER_EXPLICIT
    drill_expansion: DrillExpansion = DrillExpansion.EXPANDED_MOTIONS
    label: str = ""


@dataclass(frozen=True, slots=True)
class LinearMotion:
    id: str
    kind: MotionKind
    start: Point
    end: Point
    planned_feed_mm_min: float | None = None
    geometry_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArcMotion:
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


StudyMotion = LinearMotion | ArcMotion


@dataclass(frozen=True, slots=True)
class StudyOperationPath:
    id: str
    motions: tuple[StudyMotion, ...]
    depth_mm: float | None = None


@dataclass(frozen=True, slots=True)
class StudyToolpathPlan:
    """Study stand-in for the future canonical ToolpathPlan.

    ``planned_feed_mm_min`` is a planned path feed. It is not a CS-014
    recommendation and not an execution authority.
    """

    id: str
    operation_definition_id: str
    geometry_ids: tuple[str, ...]
    binding_id: str
    strategy_fingerprint: str
    paths: tuple[StudyOperationPath, ...]
    recommendation_id: str | None = None
    planned_feed_mm_min: float | None = None
    version: str = STUDY_VERSION


def inventory_motion_types() -> dict[str, str]:
    """Classifications matching TOOLPATH_CURRENT_STATE.md (study helper)."""
    return {
        "preview.ToolpathSegment": "VIEW PROJECTION",
        "preview.Segment": "VIEW PROJECTION",
        "models.Move": "TRANSLATION MODEL",
        "models.ArcMove": "TRANSLATION MODEL",
        "geometry.Arc2D": "UNRELATED",
        "geometry.Line2D": "UNRELATED",
        "image.etch_poly": "LEGACY",
        "StudyToolpathPlan": "CANONICAL CANDIDATE",
    }


def _signed_sweep(start: Point, end: Point, center: Point, clockwise: bool) -> float:
    """Signed sweep, same convention as ``shared.geometry._arc_sweep``.

    Coincident start/end is a full turn (2π) in the requested direction.
    """
    a0 = math.atan2(start.y - center.y, start.x - center.x)
    a1 = math.atan2(end.y - center.y, end.x - center.x)
    d = a1 - a0
    if clockwise:
        if d >= 0:
            d -= 2 * math.pi
    else:
        if d <= 0:
            d += 2 * math.pi
    return d


def _point_payload(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y, "z": point.z}


def _point_from_payload(data: dict[str, Any]) -> Point:
    return Point(float(data["x"]), float(data["y"]), float(data["z"]))


def strategy_fingerprint(strategy: StudyToolpathStrategy) -> str:
    """Computational identity of a strategy. Labels/notes are omitted."""
    payload = {
        "compensation": strategy.compensation.value,
        "drill_expansion": strategy.drill_expansion.value,
        "peck_depth_mm": strategy.peck_depth_mm,
        "retract_height_mm": strategy.retract_height_mm,
        "stepdown_mm": strategy.stepdown_mm,
        "stepover_mm": strategy.stepover_mm,
        "travel_height_mm": strategy.travel_height_mm,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return stable_id(blob, prefix="strat-")


def upstream_fingerprint(
    *,
    geometry_ids: tuple[str, ...],
    geometry_digest: str,
    definition_digest: str,
    binding_id: str,
    recommendation_digest: str | None,
    strategy: StudyToolpathStrategy,
) -> str:
    """Fingerprint of inputs that make a persisted plan stale when they change."""
    payload = {
        "binding_id": binding_id,
        "definition_digest": definition_digest,
        "geometry_digest": geometry_digest,
        "geometry_ids": list(geometry_ids),
        "recommendation_digest": recommendation_digest,
        "strategy": strategy_fingerprint(strategy),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return stable_id(blob, prefix="up-")


def make_linear(
    kind: MotionKind,
    start: Point,
    end: Point,
    *,
    index: int,
    planned_feed_mm_min: float | None = None,
    geometry_ids: tuple[str, ...] = (),
) -> LinearMotion:
    ident = stable_id(
        "linear", kind.value, start.x, start.y, start.z,
        end.x, end.y, end.z, index, prefix="lin-",
    )
    return LinearMotion(
        id=ident, kind=kind, start=start, end=end,
        planned_feed_mm_min=planned_feed_mm_min, geometry_ids=geometry_ids,
    )


def make_arc(
    start: Point,
    end: Point,
    center: Point,
    clockwise: bool,
    *,
    index: int,
    kind: MotionKind = MotionKind.CUT,
    planned_feed_mm_min: float | None = None,
    geometry_ids: tuple[str, ...] = (),
) -> ArcMotion:
    radius = math.hypot(start.x - center.x, start.y - center.y)
    sweep = _signed_sweep(start, end, center, clockwise)
    ident = stable_id(
        "arc", kind.value, start.x, start.y, start.z,
        end.x, end.y, end.z, center.x, center.y, clockwise, index,
        prefix="arc-",
    )
    return ArcMotion(
        id=ident, kind=kind, start=start, end=end, center=center,
        radius=radius, clockwise=clockwise, sweep_rad=sweep,
        planned_feed_mm_min=planned_feed_mm_min, geometry_ids=geometry_ids,
    )


def make_path(motions: tuple[StudyMotion, ...], *, index: int,
              depth_mm: float | None = None) -> StudyOperationPath:
    ident = stable_id("path", index, *(m.id for m in motions), prefix="path-")
    return StudyOperationPath(id=ident, motions=motions, depth_mm=depth_mm)


def build_study_plan(
    *,
    operation_definition_id: str,
    geometry_ids: tuple[str, ...],
    binding_id: str,
    strategy: StudyToolpathStrategy,
    paths: tuple[StudyOperationPath, ...],
    recommendation_id: str | None = None,
    planned_feed_mm_min: float | None = None,
) -> StudyToolpathPlan:
    fp = strategy_fingerprint(strategy)
    ident = stable_id(
        "plan", operation_definition_id, binding_id, fp,
        recommendation_id or "",
        planned_feed_mm_min if planned_feed_mm_min is not None else "",
        *geometry_ids, *(p.id for p in paths),
        prefix="tp-",
    )
    return StudyToolpathPlan(
        id=ident,
        operation_definition_id=operation_definition_id,
        geometry_ids=geometry_ids,
        binding_id=binding_id,
        strategy_fingerprint=fp,
        paths=paths,
        recommendation_id=recommendation_id,
        planned_feed_mm_min=planned_feed_mm_min,
    )


def depth_levels(target_depth_mm: float, stepdown_mm: float) -> tuple[float, ...]:
    """Pass Z magnitudes for a stepdown strategy. Does not rewrite target depth.

    ``target_depth_mm`` remains the final intended depth (CS-012). This helper
    only names generated levels. It is not a production stepdown algorithm.
    """
    if stepdown_mm <= 0 or target_depth_mm <= 0:
        raise ValueError("target depth and stepdown must be positive")
    levels: list[float] = []
    z = 0.0
    while z < target_depth_mm:
        z = min(z + stepdown_mm, target_depth_mm)
        levels.append(z)
    return tuple(levels)


def linear_cycle_plan(
    *,
    operation_definition_id: str = "def-contour",
    geometry_ids: tuple[str, ...] = ("geom-a",),
    binding_id: str = "bind-1",
    recommendation_id: str | None = "rec-1",
    planned_feed_mm_min: float = 800.0,
    strategy: StudyToolpathStrategy | None = None,
) -> StudyToolpathPlan:
    """Travel plunge, feed along X, retract — no G-code."""
    strategy = strategy or StudyToolpathStrategy()
    h = strategy.travel_height_mm
    feed = planned_feed_mm_min
    g = geometry_ids
    # Spec B: rapid (0,0,h)→(0,0,0), cut →(20,0,0), retract →(20,0,h).
    # Plunge is a distinct kind, demonstrated separately.
    motions = (
        make_linear(MotionKind.TRAVEL, Point(0, 0, h), Point(0, 0, 0),
                    index=0, geometry_ids=g),
        make_linear(MotionKind.CUT, Point(0, 0, 0), Point(20, 0, 0),
                    index=1, planned_feed_mm_min=feed, geometry_ids=g),
        make_linear(MotionKind.RETRACT, Point(20, 0, 0), Point(20, 0, h),
                    index=2, geometry_ids=g),
    )
    path = make_path(motions, index=0, depth_mm=0.0)
    return build_study_plan(
        operation_definition_id=operation_definition_id,
        geometry_ids=geometry_ids,
        binding_id=binding_id,
        strategy=strategy,
        paths=(path,),
        recommendation_id=recommendation_id,
        planned_feed_mm_min=planned_feed_mm_min,
    )


def expand_drill(
    xy: Point,
    *,
    target_depth_mm: float,
    strategy: StudyToolpathStrategy,
    planned_feed_mm_min: float,
    geometry_ids: tuple[str, ...] = (),
) -> tuple[LinearMotion, ...]:
    """Expand a drill into travel / plunge / peck / retract. No canned cycle."""
    travel_z = strategy.travel_height_mm
    retract_z = (strategy.retract_height_mm
                 if strategy.retract_height_mm is not None else travel_z)
    peck = strategy.peck_depth_mm
    motions: list[LinearMotion] = []
    idx = 0
    # Approach in XY at travel height, then expand pecks as signed machine Z
    # (-depth). Depth magnitudes stay on the definition; this is motion.
    motions.append(make_linear(
        MotionKind.TRAVEL, Point(0.0, 0.0, travel_z),
        Point(xy.x, xy.y, travel_z), index=idx, geometry_ids=geometry_ids,
    ))
    idx += 1
    if peck is None or peck <= 0:
        levels = (target_depth_mm,)
    else:
        levels = depth_levels(target_depth_mm, peck)
    start_z = travel_z
    current = travel_z
    for level in levels:
        cut_z = -level
        motions.append(make_linear(
            MotionKind.PLUNGE, Point(xy.x, xy.y, start_z),
            Point(xy.x, xy.y, cut_z), index=idx,
            planned_feed_mm_min=planned_feed_mm_min, geometry_ids=geometry_ids,
        ))
        idx += 1
        current = cut_z
        if level < target_depth_mm:
            motions.append(make_linear(
                MotionKind.RETRACT, Point(xy.x, xy.y, current),
                Point(xy.x, xy.y, retract_z), index=idx,
                geometry_ids=geometry_ids,
            ))
            idx += 1
            start_z = retract_z
        else:
            start_z = current
    motions.append(make_linear(
        MotionKind.RETRACT, Point(xy.x, xy.y, current),
        Point(xy.x, xy.y, travel_z), index=idx, geometry_ids=geometry_ids,
    ))
    return tuple(motions)


def compensation_rule(relation: str, tool_radius_mm: float) -> dict[str, Any]:
    """Ownership note: planner resolves explicit cutter-center offset.

    No offset algorithm. Documents *where* offset occurs for ON/INSIDE/OUTSIDE.
    """
    return {
        "owner": CompensationOwner.PLANNER_EXPLICIT.value,
        "relation": relation,
        "tool_radius_mm": tool_radius_mm,
        "offset_mm": {
            "on": 0.0,
            "inside": -tool_radius_mm,
            "outside": tool_radius_mm,
        }[relation],
        "applied_in": "toolpath_strategy_before_motion_generation",
        "not_applied_in": (
            "operation_definition",
            "gcode_controller_compensation",
        ),
    }


def cut_direction_rule(direction: str, relation: str) -> dict[str, str]:
    """Climb/conventional vs contour side and winding. No path generator."""
    return {
        "direction": direction,
        "relation": relation,
        "owner": "toolpath_strategy",
        "contour_orientation": (
            "strategy orients cutter-center path; it does not rewrite "
            "source geometry winding"
        ),
        "reversal": (
            "path reversal is a strategy/generated-motion concern, not a "
            "geometry mutation"
        ),
    }


def engagement_owner() -> dict[str, str]:
    """Single future owner for DOC/WOC/stepdown/stepover."""
    return {
        "DOC": "toolpath_strategy",
        "WOC": "toolpath_strategy",
        "stepdown": "toolpath_strategy",
        "stepover": "toolpath_strategy",
        "not": "operation_definition_or_feed_recommendation",
    }


def motion_to_dict(motion: StudyMotion) -> dict[str, Any]:
    if isinstance(motion, LinearMotion):
        return {
            "form": "linear",
            "id": motion.id,
            "kind": motion.kind.value,
            "start": _point_payload(motion.start),
            "end": _point_payload(motion.end),
            "planned_feed_mm_min": motion.planned_feed_mm_min,
            "geometry_ids": list(motion.geometry_ids),
        }
    return {
        "form": "arc",
        "id": motion.id,
        "kind": motion.kind.value,
        "start": _point_payload(motion.start),
        "end": _point_payload(motion.end),
        "center": _point_payload(motion.center),
        "radius": motion.radius,
        "clockwise": motion.clockwise,
        "sweep_rad": motion.sweep_rad,
        "planned_feed_mm_min": motion.planned_feed_mm_min,
        "geometry_ids": list(motion.geometry_ids),
    }


def motion_from_dict(data: dict[str, Any]) -> StudyMotion:
    kind = MotionKind(data["kind"])
    geometry_ids = tuple(data.get("geometry_ids") or ())
    if data["form"] == "linear":
        return LinearMotion(
            id=data["id"], kind=kind,
            start=_point_from_payload(data["start"]),
            end=_point_from_payload(data["end"]),
            planned_feed_mm_min=data.get("planned_feed_mm_min"),
            geometry_ids=geometry_ids,
        )
    return ArcMotion(
        id=data["id"], kind=kind,
        start=_point_from_payload(data["start"]),
        end=_point_from_payload(data["end"]),
        center=_point_from_payload(data["center"]),
        radius=float(data["radius"]),
        clockwise=bool(data["clockwise"]),
        sweep_rad=float(data["sweep_rad"]),
        planned_feed_mm_min=data.get("planned_feed_mm_min"),
        geometry_ids=geometry_ids,
    )


def candidate_to_dict(plan: StudyToolpathPlan) -> dict[str, Any]:
    return {
        "version": plan.version,
        "id": plan.id,
        "operation_definition_id": plan.operation_definition_id,
        "geometry_ids": list(plan.geometry_ids),
        "binding_id": plan.binding_id,
        "recommendation_id": plan.recommendation_id,
        "planned_feed_mm_min": plan.planned_feed_mm_min,
        "strategy_fingerprint": plan.strategy_fingerprint,
        "paths": [
            {
                "id": path.id,
                "depth_mm": path.depth_mm,
                "motions": [motion_to_dict(m) for m in path.motions],
            }
            for path in plan.paths
        ],
    }


def candidate_from_dict(data: dict[str, Any]) -> StudyToolpathPlan:
    paths = []
    for raw in data["paths"]:
        motions = tuple(motion_from_dict(m) for m in raw["motions"])
        paths.append(StudyOperationPath(
            id=raw["id"], motions=motions, depth_mm=raw.get("depth_mm"),
        ))
    return StudyToolpathPlan(
        id=data["id"],
        operation_definition_id=data["operation_definition_id"],
        geometry_ids=tuple(data["geometry_ids"]),
        binding_id=data["binding_id"],
        strategy_fingerprint=data["strategy_fingerprint"],
        paths=tuple(paths),
        recommendation_id=data.get("recommendation_id"),
        planned_feed_mm_min=data.get("planned_feed_mm_min"),
        version=data.get("version", STUDY_VERSION),
    )


def candidate_to_json(plan: StudyToolpathPlan) -> str:
    return json.dumps(
        candidate_to_dict(plan), sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )


def serialization_forbidden_hits(plan: StudyToolpathPlan) -> tuple[str, ...]:
    text = candidate_to_json(plan)
    hits = [tok for tok in FORBIDDEN_SERIAL_TOKENS if tok in text]
    # "Move" as a standalone JSON string / key, not as a substring of "motion".
    if '"Move"' in text or ":Move" in text:
        hits.append("Move")
    if '"safe"' in text or "safe_" in text:
        hits.append("safe")
    return tuple(hits)


def _preview_point(point: Point) -> preview.Point:
    return preview.Point(point.x, point.y, point.z)


def _preview_type(kind: MotionKind, is_arc: bool) -> str:
    if is_arc:
        return preview.ARC
    if kind is MotionKind.CUT or kind is MotionKind.PLUNGE:
        return preview.CUT
    return preview.TRAVEL


def candidate_to_preview(plan: StudyToolpathPlan) -> list[preview.ToolpathSegment]:
    """Project study motion into the existing preview model.

    Loss is intentional: preview has no planning IDs, no arc center/sweep,
    no plunge/retract kinds, and this adapter refuses to fill G-words.
    """
    segs: list[preview.ToolpathSegment] = []
    for path in plan.paths:
        for motion in path.motions:
            is_arc = isinstance(motion, ArcMotion)
            start = _preview_point(motion.start)
            end = _preview_point(motion.end)
            ptype = _preview_type(motion.kind, is_arc)
            feed = motion.planned_feed_mm_min
            if ptype == preview.TRAVEL:
                feed = None
            if is_arc:
                dist = arc_length(motion.radius, motion.sweep_rad)
            else:
                dist = distance(motion.start, motion.end)
            segs.append(preview.ToolpathSegment(
                ptype, start, end, feed, end.z, None, "", dist,
            ))
    return segs


def preview_projection_loss() -> tuple[str, ...]:
    """Canonical facts the current preview model cannot hold."""
    return (
        "operation_definition_id",
        "binding_id",
        "recommendation_id",
        "geometry_ids",
        "strategy_fingerprint",
        "motion ids",
        "plunge vs retract vs travel kinds",
        "arc center",
        "arc radius",
        "arc sweep",
        "arc clockwise flag independent of G2/G3",
        "planned vs recommended feed distinction",
        "pass depth_mm",
    )


GCODE_SEMANTIC_MAP: dict[str, str] = {
    "travel linear": "rapid move",
    "feed linear": "feed move",
    "plunge": "feed move (Z)",
    "retract": "rapid move (Z)",
    "clockwise arc": "CW arc",
    "counter-clockwise arc": "CCW arc",
}


def compare_motion_contracts() -> dict[str, str]:
    return {
        "preview.ToolpathSegment": "projected_into",
        "models.Move": "rejected_as_canonical_translation_target",
        "models.ArcMove": "rejected_as_canonical_translation_target",
        "StudyToolpathPlan": "selected_canonical_candidate",
    }
