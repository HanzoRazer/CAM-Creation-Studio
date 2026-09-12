"""Versioned JSON for a controller-neutral toolpath plan (CS-016).

The document is a sibling of an operation plan, not stored inside one.
Unknown versions and motion discriminators fail closed. Motion order is
semantically meaningful and is never sorted. ``read ≠ migration`` and
``read ≠ generation``.
"""

from __future__ import annotations

import json
import math

from ..shared.geometry import Point
from .enums import MotionKind
from .errors import ToolpathError
from .models import (
    TOOLPATH_PLAN_V1,
    ArcMotion,
    LinearMotion,
    MotionSegment,
    OperationPath,
    ToolpathPlan,
)
from .validation import validate_toolpath_plan

_MOTION_FORMS = frozenset({"linear", "arc"})


def toolpath_to_dict(plan: ToolpathPlan) -> dict:
    """JSON-ready document. No timestamps; path/motion order is preserved."""
    return {
        "version": plan.version,
        "id": plan.id,
        "operation_definition_id": plan.operation_definition_id,
        "geometry_ids": list(plan.geometry_ids),
        "binding_id": plan.binding_id,
        "recommendation_id": plan.recommendation_id,
        "planned_feed_mm_min": plan.planned_feed_mm_min,
        "strategy_fingerprint": plan.strategy_fingerprint,
        "upstream_fingerprint": plan.upstream_fingerprint,
        "paths": [
            {
                "id": path.id,
                "depth_mm": path.depth_mm,
                "motions": [_motion_to_dict(motion) for motion in path.motions],
            }
            for path in plan.paths
        ],
    }


def toolpath_from_dict(data: object) -> ToolpathPlan:
    """Rebuild a plan and structurally validate it."""
    raw = _expect_object(data, "toolpath plan document")
    if "version" not in raw:
        raise ToolpathError(
            f"not a toolpath plan document: missing version {TOOLPATH_PLAN_V1!r}")
    version = raw["version"]
    if version != TOOLPATH_PLAN_V1:
        raise ToolpathError(
            f"unknown toolpath-plan version {version!r}; "
            f"expected {TOOLPATH_PLAN_V1!r}")
    field = "toolpath plan"
    paths = tuple(
        _path_from_dict(item) for item in _expect_list(raw.get("paths"), "paths")
    )
    plan = ToolpathPlan(
        id=_nonempty(_field(raw, "id", field), "toolpath plan ID"),
        version=version,
        operation_definition_id=_nonempty(
            _field(raw, "operation_definition_id", field),
            "operation_definition_id"),
        geometry_ids=tuple(_expect_list(
            _field(raw, "geometry_ids", field), "geometry_ids")),
        binding_id=_nonempty(_field(raw, "binding_id", field), "binding_id"),
        strategy_fingerprint=_nonempty(
            _field(raw, "strategy_fingerprint", field), "strategy_fingerprint"),
        upstream_fingerprint=_nonempty(
            _field(raw, "upstream_fingerprint", field), "upstream_fingerprint"),
        paths=paths,
        recommendation_id=raw.get("recommendation_id"),
        planned_feed_mm_min=_optional_number(
            "planned_feed_mm_min", raw.get("planned_feed_mm_min")),
    )
    validate_toolpath_plan(plan)
    return plan


def toolpath_to_json(
    plan: ToolpathPlan,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """Deterministic JSON: no wall-clock fields; object keys sorted by default."""
    return json.dumps(
        toolpath_to_dict(plan), indent=indent, sort_keys=sort_keys,
        allow_nan=False)


def toolpath_from_json(text: str) -> ToolpathPlan:
    """Parse JSON and rebuild a validated plan."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolpathError(f"malformed toolpath-plan JSON: {exc}") from exc
    return toolpath_from_dict(data)


def _motion_to_dict(motion: MotionSegment) -> dict:
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
    if isinstance(motion, ArcMotion):
        return {
            "form": "arc",
            "id": motion.id,
            "kind": motion.kind.value,
            "start": _point_payload(motion.start),
            "end": _point_payload(motion.end),
            "center": _point_payload(motion.center),
            "radius": float(motion.radius),
            "clockwise": motion.clockwise,
            "sweep_rad": float(motion.sweep_rad),
            "planned_feed_mm_min": motion.planned_feed_mm_min,
            "geometry_ids": list(motion.geometry_ids),
        }
    raise ToolpathError(f"unknown motion type {type(motion)!r}")


def _path_from_dict(data: object) -> OperationPath:
    raw = _expect_object(data, "operation path")
    motions = tuple(
        _motion_from_dict(item)
        for item in _expect_list(_field(raw, "motions", "operation path"), "motions")
    )
    return OperationPath(
        id=_nonempty(_field(raw, "id", "operation path"), "operation path ID"),
        motions=motions,
        depth_mm=_optional_number("depth_mm", raw.get("depth_mm")),
    )


def _motion_from_dict(data: object) -> MotionSegment:
    raw = _expect_object(data, "motion")
    form = _field(raw, "form", "motion")
    if form not in _MOTION_FORMS:
        raise ToolpathError(f"unknown motion form {form!r}")
    kind = _kind(_field(raw, "kind", "motion"))
    geometry_ids = tuple(_expect_list(raw.get("geometry_ids") or [], "geometry_ids"))
    ident = _nonempty(_field(raw, "id", "motion"), "motion ID")
    start = _point_from_payload(_field(raw, "start", "motion"))
    end = _point_from_payload(_field(raw, "end", "motion"))
    feed = _optional_number(
        "planned_feed_mm_min", raw.get("planned_feed_mm_min"))
    if form == "linear":
        return LinearMotion(
            id=ident, kind=kind, start=start, end=end,
            planned_feed_mm_min=feed, geometry_ids=geometry_ids,
        )
    return ArcMotion(
        id=ident,
        kind=kind,
        start=start,
        end=end,
        center=_point_from_payload(_field(raw, "center", "motion")),
        radius=_require_number("radius", _field(raw, "radius", "motion")),
        clockwise=_require_bool("clockwise", _field(raw, "clockwise", "motion")),
        sweep_rad=_require_number("sweep_rad", _field(raw, "sweep_rad", "motion")),
        planned_feed_mm_min=feed,
        geometry_ids=geometry_ids,
    )


def _point_payload(point: Point) -> dict[str, float]:
    return {"x": float(point.x), "y": float(point.y), "z": float(point.z)}


def _point_from_payload(data: object) -> Point:
    raw = _expect_object(data, "point")
    return Point(
        _require_number("x", _field(raw, "x", "point")),
        _require_number("y", _field(raw, "y", "point")),
        _require_number("z", _field(raw, "z", "point")),
    )


def _kind(value: object) -> MotionKind:
    try:
        return MotionKind(value)
    except ValueError as exc:
        raise ToolpathError(f"unknown motion kind {value!r}") from exc


def _expect_object(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ToolpathError(f"{field} must be an object")
    return value


def _expect_list(value: object, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ToolpathError(f"{field} must be a list")
    return value


def _field(item: dict, name: str, field: str):
    if name not in item:
        raise ToolpathError(f"{field} is missing {name!r}")
    return item[name]


def _nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ToolpathError(f"{label} must not be empty")
    return value


def _require_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolpathError(f"{name} must be a finite number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ToolpathError(f"{name} must be a finite number, got {value!r}")
    return number


def _optional_number(name: str, value: object) -> float | None:
    if value is None:
        return None
    return _require_number(name, value)


def _require_bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ToolpathError(f"{name} must be a boolean, got {value!r}")
    return value
