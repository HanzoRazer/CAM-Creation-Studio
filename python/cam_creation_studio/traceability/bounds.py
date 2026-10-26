"""Conservative rectangular swept-volume checks for the supported witness.

The cutter is a flat cylindrical end mill of fixed radius and fixed
orientation. Material-engaging motion must keep the cutter disk, grown by
the declared positional tolerance, inside the removal rectangle. Checking
the tool centerline alone is not sufficient. Missing tolerance is refused
rather than treated as zero.

Implemented stock and fixture checks:

* axis-aligned removal rectangle versus the cutter disk on plunge and cut
* depth of plunge and cut against the declared maximum and the explicit
  depth levels
* travel and retract at or above the declared clearance
* profile, units, tool kind, and fixed orientation

Not implemented: clamp collision beyond that rectangle, full machine-body
collision, structural safety, cutting force, or machine readiness.
"""

from __future__ import annotations

import math
from dataclasses import replace

from ..shared.geometry import Point
from ..shared.numbers import round_for_gcode
from ..toolpath.enums import MotionKind
from ..toolpath.models import ArcMotion, LinearMotion, MotionSegment
from . import codes
from .compatibility import (
    DEPTH_LEVEL_ABS_TOLERANCE_MM,
    SUPPORTED_PROFILES,
    ProfileLimit,
)
from .models import PlanningRequest, Refusal

_ENGAGING = frozenset({MotionKind.CUT, MotionKind.PLUNGE})


def _disk_inside(
    x: float,
    y: float,
    radius: float,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> bool:
    return (
        x_min + radius <= x <= x_max - radius
        and y_min + radius <= y <= y_max - radius
    )


def _profile(request: PlanningRequest) -> tuple[ProfileLimit | None, Refusal | None]:
    profile = SUPPORTED_PROFILES.get(request.profile_id)
    if profile is None:
        return None, Refusal(
            codes.PROFILE_UNSUPPORTED,
            f"machine profile {request.profile_id!r} is not a supported witness profile",
        )
    if request.units != profile.units:
        return None, Refusal(
            codes.UNITS_MISMATCH,
            f"profile {profile.profile_id} does not support units {request.units!r}",
        )
    if request.tool_kind not in profile.tool_kinds:
        return None, Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            f"tool kind {request.tool_kind!r} is not supported",
        )
    if request.tool_orientation not in profile.orientations:
        return None, Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            f"tool orientation {request.tool_orientation!r} is not supported",
        )
    return profile, None


def check_declared_request(request: PlanningRequest) -> Refusal | None:
    """Check limits that are known before any motion exists."""
    _profile_value, refusal = _profile(request)
    if refusal is not None:
        return refusal
    if request.removal_max_depth_mm > request.stock_z_mm:
        return Refusal(
            codes.DEPTH_LIMIT_EXCEEDED,
            "declared removal depth exceeds the stock thickness",
        )
    for level in request.depth_levels_mm:
        if level > request.removal_max_depth_mm:
            return Refusal(
                codes.DEPTH_LIMIT_EXCEEDED,
                f"depth level {level} mm exceeds declared removal limit "
                f"{request.removal_max_depth_mm} mm",
            )
    if request.travel_height_mm < request.clearance_mm:
        return Refusal(
            codes.CLEARANCE_VIOLATION,
            "travel height is below the declared clearance",
        )
    radius = _effective_radius(request.tool_diameter_mm, request.positional_tolerance_mm)
    if isinstance(radius, Refusal):
        return radius
    x0 = request.center_x_min_mm - radius
    x1 = request.center_x_max_mm + radius
    y0 = request.center_y_min_mm - radius
    y1 = request.center_y_max_mm + radius
    if (
        x0 < request.removal_x_min_mm
        or y0 < request.removal_y_min_mm
        or x1 > request.removal_x_max_mm
        or y1 > request.removal_y_max_mm
    ):
        return Refusal(
            codes.REMOVAL_BOUND_EXCEEDED,
            "declared cutter envelope does not fit inside the removal region",
        )
    return None


def _effective_radius(
    diameter_mm: float, positional_tolerance_mm: float | None,
) -> float | Refusal:
    if positional_tolerance_mm is None:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "positional tolerance is unknown and is not assumed to be zero",
        )
    if isinstance(positional_tolerance_mm, bool) or not isinstance(
        positional_tolerance_mm, (int, float)
    ):
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "positional tolerance is unknown and is not assumed to be zero",
        )
    if not math.isfinite(float(positional_tolerance_mm)) or positional_tolerance_mm < 0:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "positional tolerance is unknown and is not assumed to be zero",
        )
    if not math.isfinite(diameter_mm) or diameter_mm <= 0:
        return Refusal(codes.UNSUPPORTED_CAPABILITY, "tool diameter is not usable")
    return float(diameter_mm) / 2.0 + float(positional_tolerance_mm)


def check_motions(
    request: PlanningRequest,
    motions: tuple[MotionSegment, ...] | list[MotionSegment],
) -> Refusal | None:
    """Check an explicit linear toolpath against the request limits."""
    declared = check_declared_request(request)
    if declared is not None:
        return declared
    radius = _effective_radius(
        request.tool_diameter_mm, request.positional_tolerance_mm)
    if isinstance(radius, Refusal):
        return radius
    if not motions:
        return Refusal(codes.UNSUPPORTED_CAPABILITY, "candidate motion is empty")
    levels = request.depth_levels_mm
    previous_end = None
    for motion in motions:
        if isinstance(motion, ArcMotion) or not isinstance(motion, LinearMotion):
            return Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                "arcs, helices, and non-linear motion are outside this witness",
            )
        values = (
            motion.start.x, motion.start.y, motion.start.z,
            motion.end.x, motion.end.y, motion.end.z,
        )
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in values):
            return Refusal(codes.UNSUPPORTED_CAPABILITY, "motion coordinates must be finite")
        if previous_end is None:
            if motion.start.z < request.clearance_mm:
                return Refusal(codes.CLEARANCE_VIOLATION, "initial pose is below clearance")
        elif motion.start != previous_end:
            return Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                "motion is discontinuous; posting must not invent an unchecked segment",
            )
        previous_end = motion.end
        if motion.kind is MotionKind.TRAVEL:
            if motion.start.z < request.clearance_mm or motion.end.z < request.clearance_mm:
                return Refusal(
                    codes.CLEARANCE_VIOLATION,
                    "a non-cutting move enters the declared clearance",
                )
            continue
        if motion.kind is MotionKind.RETRACT:
            if motion.end.z < request.clearance_mm or motion.end.z < motion.start.z:
                return Refusal(
                    codes.CLEARANCE_VIOLATION,
                    "a retract does not finish at or above the declared clearance",
                )
            if motion.start.x != motion.end.x or motion.start.y != motion.end.y:
                return Refusal(
                    codes.UNSUPPORTED_CAPABILITY, "only vertical retracts are supported")
            continue
        if motion.kind not in _ENGAGING:
            return Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                f"motion kind {motion.kind!r} is outside this witness",
            )
        refusal = _check_engaging(request, motion, radius, levels)
        if refusal is not None:
            return refusal
    if previous_end.z < request.clearance_mm:
        return Refusal(codes.CLEARANCE_VIOLATION, "final pose is below clearance")
    return None


def _check_engaging(
    request: PlanningRequest,
    motion: LinearMotion,
    radius: float,
    levels: tuple[float, ...],
) -> Refusal | None:
    if (
        motion.kind is MotionKind.CUT and motion.start.z != motion.end.z
    ) or (
        motion.kind is MotionKind.PLUNGE
        and (motion.start.x != motion.end.x or motion.start.y != motion.end.y
             or motion.end.z > motion.start.z)
    ):
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "only level cuts and vertical downward plunges are supported",
        )
    for x, y, z in _engaging_points(motion):
        if z > 0:
            continue
        if not _disk_inside(
            x,
            y,
            radius,
            request.removal_x_min_mm,
            request.removal_y_min_mm,
            request.removal_x_max_mm,
            request.removal_y_max_mm,
        ):
            return Refusal(
                codes.REMOVAL_BOUND_EXCEEDED,
                "cutter envelope leaves the removal region",
            )
        if z == 0:
            continue
        depth = -z
        matches_level = any(math.isclose(
            depth, level, rel_tol=0.0, abs_tol=DEPTH_LEVEL_ABS_TOLERANCE_MM,
        ) for level in levels)
        # Epsilon accommodates floating-point identity only. It never extends
        # the hard maximum removal depth.
        if depth > request.removal_max_depth_mm or not matches_level:
            return Refusal(
                codes.DEPTH_LIMIT_EXCEEDED,
                f"engaging Z {z} mm is outside the declared depth levels "
                f"and removal limit",
            )
    return None


def check_posting_precision(
    request: PlanningRequest, motions: tuple[MotionSegment, ...] | list[MotionSegment],
) -> Refusal | None:
    """Recheck the coordinates the existing three-decimal formatter emits.

    Original motion must pass check_motions first. Rounding must not move a
    cutter outside a hard bound or lower the header/footer below clearance.
    """
    if round_for_gcode(request.clearance_mm) < request.clearance_mm:
        return Refusal(codes.CLEARANCE_VIOLATION, "posted clearance rounds below its limit")
    rounded = []
    for motion in motions:
        if not isinstance(motion, LinearMotion):
            return Refusal(codes.UNSUPPORTED_CAPABILITY, "only linear posting is supported")
        points = [Point(*(round_for_gcode(v) for v in (p.x, p.y, p.z)))
                  for p in (motion.start, motion.end)]
        rounded.append(replace(motion, start=points[0], end=points[1]))
    return check_motions(request, rounded)


def _engaging_points(motion: LinearMotion) -> tuple[tuple[float, float, float], ...]:
    """Endpoints of the portion of a segment at or below the stock top."""
    start = (motion.start.x, motion.start.y, motion.start.z)
    end = (motion.end.x, motion.end.y, motion.end.z)
    if start[2] <= 0 and end[2] <= 0:
        return (start, end)
    if start[2] > 0 and end[2] > 0:
        return ()
    high, low = (start, end) if start[2] > end[2] else (end, start)
    span = low[2] - high[2]
    if span == 0:
        return (low,)
    t = (0.0 - high[2]) / span
    surface = (
        high[0] + t * (low[0] - high[0]),
        high[1] + t * (low[1] - high[1]),
        0.0,
    )
    return (surface, low)
