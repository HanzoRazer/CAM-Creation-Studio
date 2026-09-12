"""Structural validation for controller-neutral toolpath documents (CS-016).

This checks identity, numeric fields, analytic-arc consistency, and
in-path continuity. It does not judge whether a path is a sensible
machining choice, and it does not claim machine readiness.
"""

from __future__ import annotations

import math

from ..shared.geometry import Point, distance_2d
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

# Millimetre / radian slack for reconstructed analytic fields.
_ARC_TOL = 1e-7
_TWO_PI = 2.0 * math.pi


def validate_toolpath_plan(plan: ToolpathPlan) -> None:
    """Raise if ``plan`` is structurally invalid. Returns ``None`` when valid."""
    if plan.version != TOOLPATH_PLAN_V1:
        raise ToolpathError(
            f"unknown toolpath-plan version {plan.version!r}; "
            f"expected {TOOLPATH_PLAN_V1!r}")
    if not plan.id:
        raise ToolpathError("toolpath plan ID must not be empty")
    if not plan.operation_definition_id:
        raise ToolpathError("operation_definition_id must not be empty")
    if not plan.binding_id:
        raise ToolpathError("binding_id must not be empty")
    if not plan.geometry_ids:
        raise ToolpathError("geometry_ids must not be empty")
    if not plan.strategy_fingerprint:
        raise ToolpathError("strategy_fingerprint must not be empty")
    if not plan.upstream_fingerprint:
        raise ToolpathError("upstream_fingerprint must not be empty")
    _optional_positive_feed("planned_feed_mm_min", plan.planned_feed_mm_min)
    if not plan.paths:
        raise ToolpathError("machining toolpath plan must contain at least one path")

    path_ids: set[str] = set()
    motion_ids: set[str] = set()
    plan_geometry = set(plan.geometry_ids)
    for path in plan.paths:
        _validate_path(path, path_ids, motion_ids, plan_geometry)


def signed_sweep(
    start: Point, end: Point, center: Point, clockwise: bool,
) -> float:
    """Signed XY sweep, same convention as ``shared.geometry._arc_sweep``.

    Coincident start/end is a full turn (2π) in the requested direction.
    """
    a0 = math.atan2(start.y - center.y, start.x - center.x)
    a1 = math.atan2(end.y - center.y, end.x - center.x)
    d = a1 - a0
    if clockwise:
        if d >= 0:
            d -= _TWO_PI
    else:
        if d <= 0:
            d += _TWO_PI
    return d


def _validate_path(
    path: OperationPath,
    path_ids: set[str],
    motion_ids: set[str],
    plan_geometry: set[str],
) -> None:
    if not path.id:
        raise ToolpathError("operation path ID must not be empty")
    if path.id in path_ids:
        raise ToolpathError(f"duplicate operation path ID {path.id!r}")
    path_ids.add(path.id)
    if not path.motions:
        raise ToolpathError(f"operation path {path.id!r} must contain motions")
    if path.depth_mm is not None:
        _require_finite("depth_mm", path.depth_mm)

    previous: MotionSegment | None = None
    for motion in path.motions:
        if not motion.id:
            raise ToolpathError("motion ID must not be empty")
        if motion.id in motion_ids:
            raise ToolpathError(f"duplicate motion ID {motion.id!r}")
        motion_ids.add(motion.id)
        _validate_motion(motion, plan_geometry)
        if previous is not None and previous.end != motion.start:
            raise ToolpathError(
                f"discontinuous motions {previous.id!r} → {motion.id!r}; "
                "split them into separate operation paths")
        previous = motion


def _validate_motion(motion: MotionSegment, plan_geometry: set[str]) -> None:
    if not isinstance(motion.kind, MotionKind):
        raise ToolpathError(f"unknown motion kind {motion.kind!r}")
    _require_point("start", motion.start)
    _require_point("end", motion.end)
    _optional_positive_feed("planned_feed_mm_min", motion.planned_feed_mm_min)
    _validate_geometry_ids(motion.geometry_ids, plan_geometry)
    if isinstance(motion, LinearMotion):
        if motion.start == motion.end:
            raise ToolpathError(
                f"linear motion {motion.id!r} has coincident start and end")
        return
    if isinstance(motion, ArcMotion):
        _validate_arc(motion)
        return
    raise ToolpathError(f"unknown motion type {type(motion)!r}")


def _validate_arc(motion: ArcMotion) -> None:
    _require_point("center", motion.center)
    radius = _require_finite("radius", motion.radius)
    if radius <= 0:
        raise ToolpathError(
            f"arc {motion.id!r} radius must be greater than 0, got {radius}")
    sweep = _require_finite("sweep_rad", motion.sweep_rad)
    if motion.clockwise and sweep > _ARC_TOL:
        raise ToolpathError(
            f"clockwise arc {motion.id!r} must have sweep_rad ≤ 0")
    if not motion.clockwise and sweep < -_ARC_TOL:
        raise ToolpathError(
            f"counter-clockwise arc {motion.id!r} must have sweep_rad ≥ 0")

    start_r = distance_2d(motion.start, motion.center)
    end_r = distance_2d(motion.end, motion.center)
    if abs(start_r - radius) > _ARC_TOL or abs(end_r - radius) > _ARC_TOL:
        raise ToolpathError(
            f"arc {motion.id!r} radius is inconsistent with start/end and center")

    expected = signed_sweep(
        motion.start, motion.end, motion.center, motion.clockwise)
    if motion.start == motion.end:
        if abs(abs(sweep) - _TWO_PI) > _ARC_TOL:
            raise ToolpathError(
                f"arc {motion.id!r} with coincident endpoints must be a "
                "full turn (|sweep| = 2π), not a zero-length arc")
        return
    if abs(sweep - expected) > _ARC_TOL:
        raise ToolpathError(
            f"arc {motion.id!r} sweep_rad does not match start/end/center")
    if abs(sweep) <= _ARC_TOL:
        raise ToolpathError(f"arc {motion.id!r} has zero sweep")


def _validate_geometry_ids(
    geometry_ids: tuple[str, ...], plan_geometry: set[str],
) -> None:
    if not geometry_ids:
        return
    extra = [gid for gid in geometry_ids if gid not in plan_geometry]
    if extra:
        raise ToolpathError(
            f"motion geometry_ids {extra} are not a subset of the plan")


def _require_point(name: str, point: Point) -> None:
    _require_finite(f"{name}.x", point.x)
    _require_finite(f"{name}.y", point.y)
    _require_finite(f"{name}.z", point.z)


def _optional_positive_feed(name: str, value: float | None) -> None:
    if value is None:
        return
    number = _require_finite(name, value)
    if number <= 0:
        raise ToolpathError(f"{name} must be greater than 0, got {number}")


def _require_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolpathError(f"{name} must be a finite number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ToolpathError(f"{name} must be a finite number, got {value!r}")
    return number
