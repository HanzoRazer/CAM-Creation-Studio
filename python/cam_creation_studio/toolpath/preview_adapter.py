"""Project a ``ToolpathPlan`` into the existing preview model (CS-016).

Preview is a lossy view. This adapter constructs ``ToolpathSegment`` values
at the package boundary and does not store them on the plan. Canonical
``ArcMotion`` stays analytic; a full-circle arc (coincident endpoints) is
tessellated only in this projection so the view is not a zero-length chord.
"""

from __future__ import annotations

from itertools import pairwise

from ..preview import toolpath_model as preview
from ..shared.geometry import Point, arc_length, distance, interpolate_arc
from .enums import MotionKind
from .models import ArcMotion, ToolpathPlan

_FULL_CIRCLE_SEGMENTS = 40


def toolpath_to_preview(plan: ToolpathPlan) -> list[preview.ToolpathSegment]:
    """Project planned motion into ``preview.ToolpathSegment``.

    Mapping:

    * ``travel`` / ``retract`` → preview ``travel`` (feed ``None``)
    * ``cut`` / ``plunge`` → preview ``cut``
    * non-full ``ArcMotion`` → preview ``arc``
    * full-circle ``ArcMotion`` → tessellated linear preview segments

    ``source_command`` is left empty. This adapter does not invent G-words.
    """
    segs: list[preview.ToolpathSegment] = []
    for path in plan.paths:
        for motion in path.motions:
            if isinstance(motion, ArcMotion) and motion.start == motion.end:
                segs.extend(_tessellate_full_circle(motion))
                continue
            is_arc = isinstance(motion, ArcMotion)
            start = _preview_point(motion.start)
            end = _preview_point(motion.end)
            ptype = _preview_type(motion.kind, is_arc)
            feed = None if ptype == preview.TRAVEL else motion.planned_feed_mm_min
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
        "upstream_fingerprint",
        "motion ids",
        "plunge vs retract vs travel kinds",
        "arc center",
        "arc radius",
        "arc sweep",
        "arc clockwise flag independent of G2/G3",
        "planned vs recommended feed distinction",
        "pass depth_mm",
    )


def _tessellate_full_circle(motion: ArcMotion) -> list[preview.ToolpathSegment]:
    i = motion.center.x - motion.start.x
    j = motion.center.y - motion.start.y
    points = interpolate_arc(
        motion.start, motion.end, i, j, motion.clockwise,
        segments=_FULL_CIRCLE_SEGMENTS,
    )
    ptype = _preview_type(motion.kind, is_arc=False)
    feed = None if ptype == preview.TRAVEL else motion.planned_feed_mm_min
    segs: list[preview.ToolpathSegment] = []
    for prev, nxt in pairwise(points):
        end = _preview_point(nxt)
        dist = distance(prev, nxt)
        segs.append(preview.ToolpathSegment(
            ptype, _preview_point(prev), end, feed, end.z, None, "", dist,
        ))
    return segs


def _preview_point(point: Point) -> preview.Point:
    return preview.Point(point.x, point.y, point.z)


def _preview_type(kind: MotionKind, is_arc: bool) -> str:
    if is_arc:
        return preview.ARC
    if kind is MotionKind.CUT or kind is MotionKind.PLUNGE:
        return preview.CUT
    return preview.TRAVEL
