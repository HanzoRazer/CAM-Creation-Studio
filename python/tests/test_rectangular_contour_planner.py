"""Bounded rectangular centerline planner.

Expected motion is written out here. It is not produced by the planner
helper under test.
"""

from __future__ import annotations

import inspect
import math

import pytest
from dataclasses import replace

from cam_creation_studio.geometry.models import Arc2D, Line2D
from cam_creation_studio.planning.errors import PlanningError
from cam_creation_studio.planning.models import RectangularPlannerOptions
from cam_creation_studio.planning.rectangular import (
    expand_rectangular_contour,
    normalize_rectangle,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.preview_adapter import (
    preview_projection_loss,
    toolpath_to_preview,
)
from cam_creation_studio.toolpath.serialization import (
    toolpath_from_json,
    toolpath_to_json,
)
from cam_creation_studio.traceability.bounds import (
    check_motions,
    check_posting_precision,
)
from cam_creation_studio.traceability.service import verify_package
from cam_creation_studio.traceability.synthetic import build_synthetic_package
from tests.support.rectangle_planned import (
    CENTER,
    CUT_FEED,
    DEPTH_LEVELS,
    MAX_DEPTH_MM,
    PLUNGE_FEED,
    TARGET_DEPTH_MM,
    golden_lines,
    make_operation_plan,
    write_planned_package,
)

X0, Y0, X1, Y1 = CENTER
TRAVEL = 5


def _expected_rows():
    """Handwritten golden poses for depths 1 mm and 2 mm."""
    rows = []
    for depth in (1, 2):
        z = -depth
        rows.append(("plunge", (X0, Y0, TRAVEL), (X0, Y0, z), PLUNGE_FEED))
        rows.append(("cut", (X0, Y0, z), (X1, Y0, z), CUT_FEED))
        rows.append(("cut", (X1, Y0, z), (X1, Y1, z), CUT_FEED))
        rows.append(("cut", (X1, Y1, z), (X0, Y1, z), CUT_FEED))
        rows.append(("cut", (X0, Y1, z), (X0, Y0, z), CUT_FEED))
        rows.append(("retract", (X0, Y0, z), (X0, Y0, TRAVEL), None))
    return rows


def _options(**overrides) -> RectangularPlannerOptions:
    values = {
        "planned_cut_feed_mm_min": CUT_FEED,
        "planned_plunge_feed_mm_min": PLUNGE_FEED,
        "recommendation_id": None,
        "depth_levels_mm": DEPTH_LEVELS,
        "travel_height_mm": TRAVEL,
        "clearance_mm": TRAVEL,
        "stepdown_mm": 1.0,
        "removal_max_depth_mm": MAX_DEPTH_MM,
        "stock_allowance_mm": 0.0,
    }
    values.update(overrides)
    return RectangularPlannerOptions(**values)


def _expand(plan=None, **overrides):
    operation = plan if plan is not None else make_operation_plan()
    return operation, expand_rectangular_contour(
        operation, operation.definitions[0].id, _options(**overrides))


def _flat(expansion):
    return tuple(motion for path in expansion.plan.paths for motion in path.motions)


def _pose(point: Point):
    return (point.x, point.y, point.z)


def test_limit_is_not_a_caller_argument():
    assert "max_motions" not in inspect.signature(
        expand_rectangular_contour).parameters
    assert "max_depth_levels" not in inspect.signature(
        expand_rectangular_contour).parameters


def test_golden_rectangle_matches_handwritten_motion():
    _operation, expansion = _expand()
    motions = _flat(expansion)
    expected = _expected_rows()
    assert len(expansion.plan.paths) == 2
    assert [path.depth_mm for path in expansion.plan.paths] == [1.0, 2.0]
    assert len(motions) == 12
    assert len(expected) == 12
    kinds = [row[0] for row in expected]
    assert kinds.count("cut") == 8
    assert kinds.count("plunge") == 2
    assert kinds.count("retract") == 2
    horizontal = 0.0
    for row, motion in zip(expected, motions):
        kind, start, end, feed = row
        assert motion.kind.value == kind
        assert _pose(motion.start) == start
        assert _pose(motion.end) == end
        assert motion.start != motion.end
        assert motion.planned_feed_mm_min == feed
        if kind == "cut":
            horizontal += abs(end[0] - start[0]) + abs(end[1] - start[1])
    assert horizontal == 240
    assert motions[-1].end.z == 5
    for path in expansion.plan.paths:
        cuts = [item for item in path.motions if item.kind is MotionKind.CUT]
        assert _pose(cuts[0].start)[:2] == (X0, Y0)
        assert _pose(cuts[-1].end)[:2] == (X0, Y0)
        assert cuts[0].start.z == cuts[-1].end.z
    assert motions[5].end == motions[6].start


def test_canonical_plan_keeps_real_operation_identities():
    operation, expansion = _expand()
    plan = expansion.plan
    assert plan.operation_definition_id == operation.definitions[0].id
    assert plan.binding_id == operation.bindings[0].id
    assert plan.geometry_ids == operation.workspace.selections[0].entity_ids
    assert plan.recommendation_id is None
    assert operation.recommendations
    assert plan.version == "camstudio_toolpath_v1"
    selected = _options(recommendation_id=operation.recommendations[0].id)
    attached = expand_rectangular_contour(
        operation, operation.definitions[0].id, selected)
    assert attached.plan.recommendation_id == operation.recommendations[0].id


def test_preview_is_a_projection_of_the_same_plan():
    _operation, expansion = _expand()
    segments = toolpath_to_preview(expansion.plan)
    assert len(segments) == 12
    assert segments[0].start.z == TRAVEL
    assert segments[-1].end.z == TRAVEL
    assert "operation_definition_id" in preview_projection_loss()
    restored = toolpath_from_json(toolpath_to_json(expansion.plan))
    assert restored.id == expansion.plan.id
    assert len(restored.paths) == 2


def test_rectangle_normalization_is_independent_of_edge_order():
    operation = make_operation_plan()
    selection = operation.workspace.selections[0]
    edges = []
    for entity_id in reversed(selection.entity_ids):
        entity = operation.workspace.geometry.entities[
            next(ref.entity_index for ref in operation.workspace.geometry_refs
                 if ref.id == entity_id)
        ]
        edges.append((entity_id, Line2D(entity.end, entity.start)))
    rectangle = normalize_rectangle(edges)
    assert (rectangle.x_min_mm, rectangle.y_min_mm,
            rectangle.x_max_mm, rectangle.y_max_mm) == CENTER
    flipped = [Line2D(line.end, line.start) for line in golden_lines()]
    permuted = flipped[2:] + flipped[:2]
    planned = make_operation_plan(permuted)
    expansion = expand_rectangular_contour(
        planned, planned.definitions[0].id, _options())
    actual = [
        (
            motion.kind.value,
            _pose(motion.start),
            _pose(motion.end),
            motion.planned_feed_mm_min,
        )
        for motion in _flat(expansion)
    ]
    assert actual == _expected_rows()


@pytest.mark.parametrize("lines", [
    golden_lines()[:3],
    golden_lines() + [Line2D(Point(0, 0, 0), Point(1, 0, 0))],
    [Line2D(Point(20, 15, 0), Point(60, 15, 0))] * 4,
    [
        Line2D(Point(20, 15, 0), Point(40, 15, 0)),
        Line2D(Point(60, 15, 0), Point(60, 35, 0)),
        Line2D(Point(60, 35, 0), Point(20, 35, 0)),
        Line2D(Point(20, 35, 0), Point(20, 15, 0)),
    ],
    [
        Line2D(Point(20, 15, 0), Point(60, 35, 0)),
        Line2D(Point(60, 35, 0), Point(20, 35, 0)),
        Line2D(Point(20, 35, 0), Point(60, 15, 0)),
        Line2D(Point(60, 15, 0), Point(20, 15, 0)),
    ],
    [
        Line2D(Point(20, 15, 0), Point(40, 25, 0)),
        Line2D(Point(40, 25, 0), Point(60, 15, 0)),
        Line2D(Point(60, 15, 0), Point(40, 5, 0)),
        Line2D(Point(40, 5, 0), Point(20, 15, 0)),
    ],
])
def test_rejects_edges_that_are_not_one_rectangle(lines):
    operation = make_operation_plan(lines)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation, operation.definitions[0].id, _options())
    assert caught.value.code == "UNSUPPORTED_CAPABILITY"


def test_rejects_curves_and_nonplanar_edges():
    arc = Arc2D(Point(40, 25, 0), 10, 0, 90)
    operation = make_operation_plan([arc, *golden_lines()[:3]])
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation, operation.definitions[0].id, _options())
    assert caught.value.code == "UNSUPPORTED_CAPABILITY"
    raised = [
        Line2D(Point(20, 15, 1), Point(60, 15, 1)),
        *golden_lines()[1:],
    ]
    operation = make_operation_plan(raised)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation, operation.definitions[0].id, _options())
    assert "Z0" in caught.value.detail


@pytest.mark.parametrize("kwargs", [
    {"relation": "inside"},
    {"relation": "outside"},
    {"direction": "climb"},
    {"direction": "conventional"},
    {"allowance": 0.2},
    {"allowance": None},
])
def test_rejects_relation_direction_and_allowance(kwargs):
    operation = make_operation_plan(**kwargs)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation, operation.definitions[0].id, _options())
    assert caught.value.code == "UNSUPPORTED_CAPABILITY"


@pytest.mark.parametrize("overrides", [
    {"depth_levels_mm": (2.0, 1.0)},
    {"depth_levels_mm": (1.0, 1.0)},
    {"depth_levels_mm": (1.0, math.nan)},
    {"depth_levels_mm": (0.0, 2.0)},
    {"depth_levels_mm": (-1.0, 2.0)},
    {"depth_levels_mm": (1.0, 2.0), "stepdown_mm": 0.5},
    {
        "depth_levels_mm": (1.0, 4.0),
        "removal_max_depth_mm": 3.0,
        "stepdown_mm": 4.0,
    },
])
def test_rejects_depth_levels(overrides):
    target = overrides["depth_levels_mm"][-1]
    if not math.isfinite(target) or target <= 0:
        target = TARGET_DEPTH_MM
    removal = overrides.get("removal_max_depth_mm", max(MAX_DEPTH_MM, target))
    operation = make_operation_plan(target_depth_mm=target)
    values = dict(overrides)
    values["removal_max_depth_mm"] = removal
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation, operation.definitions[0].id, _options(**values))
    assert caught.value.code == "DEPTH_LIMIT_EXCEEDED"


def test_final_depth_must_match_the_definition():
    operation = make_operation_plan(target_depth_mm=2.0)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation,
            operation.definitions[0].id,
            _options(depth_levels_mm=(1.0, 1.5)),
        )
    assert caught.value.code == "DEPTH_LIMIT_EXCEEDED"


def test_unrepresentable_numeric_options_are_refused():
    operation = make_operation_plan()
    definition_id = operation.definitions[0].id
    for overrides in (
        {"planned_cut_feed_mm_min": 10**1000},
        {"planned_plunge_feed_mm_min": 10**1000},
        {"depth_levels_mm": (10**1000,)},
        {"stepdown_mm": 10**1000},
        {"removal_max_depth_mm": 10**1000},
        {"travel_height_mm": 10**1000},
        {"clearance_mm": 10**1000},
    ):
        with pytest.raises(PlanningError) as caught:
            expand_rectangular_contour(operation, definition_id, _options(**overrides))
        assert caught.value.code == "SCHEMA_INVALID"
        assert "finite number" in caught.value.detail


@pytest.mark.parametrize("feed", [None, 0, -5, math.nan, math.inf, 0.0004, True])
def test_rejects_missing_or_nonpositive_feeds(feed):
    operation = make_operation_plan()
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            operation,
            operation.definitions[0].id,
            _options(planned_cut_feed_mm_min=feed),
        )
    assert caught.value.code == "UNSUPPORTED_CAPABILITY"
    with pytest.raises(PlanningError):
        expand_rectangular_contour(
            operation,
            operation.definitions[0].id,
            _options(planned_plunge_feed_mm_min=feed),
        )


def test_resource_limits_refuse_before_motion_allocation(monkeypatch):
    calls = []

    def _forbid(*_args, **_kwargs):
        calls.append(1)
        raise AssertionError("motion was allocated past the limit")

    monkeypatch.setattr(
        "cam_creation_studio.planning.rectangular.make_linear_motion", _forbid)
    deep = make_operation_plan(target_depth_mm=9)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            deep, deep.definitions[0].id,
            _options(
                depth_levels_mm=tuple(float(i) for i in range(1, 10)),
                removal_max_depth_mm=9,
            ),
        )
    assert caught.value.code == "UNSUPPORTED_CAPABILITY"
    wide = make_operation_plan(target_depth_mm=4)
    with pytest.raises(PlanningError) as caught:
        expand_rectangular_contour(
            wide, wide.definitions[0].id,
            _options(
                depth_levels_mm=(1.0, 2.0, 3.0, 4.0),
                removal_max_depth_mm=4,
            ),
        )
    assert "motion count" in caught.value.detail
    assert calls == []


def test_bounds_checker_accepts_clearance_and_refuses_a_corrupt_endpoint(tmp_path):
    package = write_planned_package(tmp_path / "pkg")
    request = verify_package(package).request
    _operation, expansion = _expand()
    motions = list(_flat(expansion))
    assert check_motions(request, motions) is None
    assert check_posting_precision(request, motions) is None
    z = motions[2].end.z
    moved = Point(0, motions[2].end.y, z)
    corrupted = list(motions)
    corrupted[2] = replace(motions[2], end=moved)
    corrupted[3] = replace(motions[3], start=moved)
    refusal = check_motions(request, corrupted)
    assert refusal is not None
    assert refusal.code == "REMOVAL_BOUND_EXCEEDED"


def test_bounds_checker_boundary_cases_stay_independent(tmp_path):
    from cam_creation_studio.toolpath.builders import make_linear_motion

    package = write_planned_package(tmp_path / "pkg")
    request = verify_package(package).request
    x0, y0, x1, y1 = CENTER

    def linear(kind, start, end, index, feed=None):
        return make_linear_motion(
            kind, start, end, index=index, planned_feed_mm_min=feed)

    surface = [
        linear(MotionKind.PLUNGE, Point(x0, y0, 5), Point(x0, y0, 0), 0, 300),
        linear(MotionKind.CUT, Point(x0, y0, 0), Point(x1, y0, 0), 1, 800),
        linear(MotionKind.CUT, Point(x1, y0, 0), Point(x1, y1, 0), 2, 800),
        linear(MotionKind.CUT, Point(x1, y1, 0), Point(x0, y1, 0), 3, 800),
        linear(MotionKind.CUT, Point(x0, y1, 0), Point(x0, y0, 0), 4, 800),
        linear(MotionKind.RETRACT, Point(x0, y0, 0), Point(x0, y0, 5), 5),
    ]
    assert check_motions(request, surface) is None

    ramp = [
        linear(MotionKind.PLUNGE, Point(x0, y0, 5), Point(x1, y0, -1), 0, 300),
        linear(MotionKind.RETRACT, Point(x1, y0, -1), Point(x1, y0, 5), 1),
    ]
    assert check_motions(request, ramp).code == "UNSUPPORTED_CAPABILITY"

    lateral = [
        linear(MotionKind.PLUNGE, Point(x0, y0, 5), Point(x0, y0, -1), 0, 300),
        linear(MotionKind.RETRACT, Point(x0, y0, -1), Point(x1, y0, 5), 1),
    ]
    assert check_motions(request, lateral).code == "UNSUPPORTED_CAPABILITY"

    gap = [
        linear(MotionKind.PLUNGE, Point(x0, y0, 5), Point(x0, y0, -1), 0, 300),
        linear(MotionKind.CUT, Point(x0, y0 + 1, -1), Point(x1, y0, -1), 1, 800),
    ]
    assert check_motions(request, gap).code == "UNSUPPORTED_CAPABILITY"

    low = [linear(MotionKind.TRAVEL, Point(x0, y0, 4), Point(x1, y0, 4), 0)]
    assert check_motions(request, low).code == "CLEARANCE_VIOLATION"

    outside = [
        linear(MotionKind.PLUNGE, Point(0, 0, 5), Point(0, 0, -1), 0, 300),
        linear(MotionKind.RETRACT, Point(0, 0, -1), Point(0, 0, 5), 1),
    ]
    assert check_motions(request, outside).code == "REMOVAL_BOUND_EXCEEDED"

    coupon = build_synthetic_package(tmp_path / "coupon")
    coupon_request = verify_package(coupon).request
    assert check_motions(coupon_request, motions_of_coupon()) is None


def motions_of_coupon():
    """The historical explicit coupon, built here rather than by the planner."""
    from cam_creation_studio.toolpath.builders import make_linear_motion
    from cam_creation_studio.traceability.synthetic import CENTER as coupon_center
    from cam_creation_studio.traceability.synthetic import DEPTH_LEVELS as levels

    x0, y0, x1, y1 = coupon_center
    motions = []
    index = 0
    for depth in levels:
        z = -depth
        motions.append(make_linear_motion(
            MotionKind.PLUNGE, Point(x0, y0, 5), Point(x0, y0, z),
            index=index, planned_feed_mm_min=300))
        index += 1
        previous = Point(x0, y0, z)
        for corner in (
            Point(x1, y0, z), Point(x1, y1, z), Point(x0, y1, z), Point(x0, y0, z),
        ):
            motions.append(make_linear_motion(
                MotionKind.CUT, previous, corner, index=index,
                planned_feed_mm_min=800))
            index += 1
            previous = corner
        motions.append(make_linear_motion(
            MotionKind.RETRACT, previous, Point(x0, y0, 5), index=index))
        index += 1
    return tuple(motions)
