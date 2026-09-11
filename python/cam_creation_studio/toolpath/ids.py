"""Deterministic toolpath identifiers (CS-016).

IDs are a creation-context identity, matching CS-011–CS-014: kind, poses,
parent ids, and how many objects already exist. Equivalent helper sequences
therefore produce equivalent IDs. Random identifiers are not used.
"""

from __future__ import annotations

from ..shared.geometry import Point
from ..shared.ids import stable_id


def make_motion_id(
    form: str,
    kind: str,
    start: Point,
    end: Point,
    *,
    index: int,
    center: Point | None = None,
    clockwise: bool | None = None,
) -> str:
    """Stable ID for one linear or arc motion at creation time."""
    if form == "linear":
        return stable_id(
            "linear", kind, start.x, start.y, start.z,
            end.x, end.y, end.z, index,
            prefix="lin-",
        )
    if form == "arc":
        if center is None or clockwise is None:
            raise ValueError("arc motion IDs require center and clockwise")
        return stable_id(
            "arc", kind, start.x, start.y, start.z,
            end.x, end.y, end.z, center.x, center.y, center.z,
            clockwise, index,
            prefix="arc-",
        )
    raise ValueError(f"unknown motion form {form!r}")


def make_operation_path_id(
    *motion_ids: str,
    existing_count: int,
) -> str:
    """Stable ID for an operation path at creation time."""
    return stable_id(
        "path", existing_count, *motion_ids,
        prefix="path-",
    )


def make_path_id(
    *motion_ids: str,
    existing_count: int,
) -> str:
    """Alias for :func:`make_operation_path_id`."""
    return make_operation_path_id(*motion_ids, existing_count=existing_count)


def make_toolpath_id(
    operation_definition_id: str,
    binding_id: str,
    strategy_fingerprint: str,
    *geometry_ids: str,
    recommendation_id: str | None = None,
    planned_feed_mm_min: float | None = None,
    path_ids: tuple[str, ...] = (),
    existing_count: int = 0,
) -> str:
    """Stable ID for a toolpath plan at creation time."""
    return stable_id(
        "plan",
        operation_definition_id,
        binding_id,
        strategy_fingerprint,
        recommendation_id or "",
        "" if planned_feed_mm_min is None else planned_feed_mm_min,
        existing_count,
        *geometry_ids,
        *path_ids,
        prefix="tp-",
    )
