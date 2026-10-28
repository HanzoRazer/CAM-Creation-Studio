"""Signed-zero normalization for the rectangular centerline planner.

Expected poses are written here. They are not copied from the planner output.
Zero sign is checked with ``math.copysign`` because numeric equality treats
``-0.0`` and ``0.0`` as the same value.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from cam_creation_studio.geometry.models import Line2D
from cam_creation_studio.operations.serialization import operation_plan_to_json
from cam_creation_studio.planning.errors import PlanningError
from cam_creation_studio.planning.models import RectangularPlannerOptions
from cam_creation_studio.planning.rectangular import (
    expand_rectangular_contour,
    normalize_rectangle,
)
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.fingerprint import strategy_fingerprint
from cam_creation_studio.toolpath.models import ToolpathStrategy
from cam_creation_studio.toolpath.serialization import toolpath_to_json
from cam_creation_studio.traceability.service import (
    evaluate_explicit_motion_export,
    plan_digest_for,
    run_witness,
    verify_package,
)
from cam_creation_studio.traceability.synthetic import build_synthetic_package
from cam_creation_studio.toolpath.builders import make_linear_motion
from support.fixture_review import fixture_review_bytes
from support.rectangle_planned import (
    CENTER,
    CUT_FEED,
    PLUNGE_FEED,
    golden_lines,
    make_operation_plan,
    write_planned_package,
)

_WIDTH = 4.0
_HEIGHT = 3.0
_TRAVEL = 5.0
_DEPTH = 1.0


def _mixed_sides() -> list[Line2D]:
    """One rectangle whose corners use both signs of zero."""
    return [
        Line2D(Point(-0.0, -0.0, 0.0), Point(_WIDTH, 0.0, 0.0)),
        Line2D(Point(_WIDTH, -0.0, 0.0), Point(_WIDTH, _HEIGHT, 0.0)),
        Line2D(Point(_WIDTH, _HEIGHT, 0.0), Point(0.0, _HEIGHT, 0.0)),
        Line2D(Point(0.0, _HEIGHT, 0.0), Point(-0.0, 0.0, 0.0)),
    ]


def _options(**overrides) -> RectangularPlannerOptions:
    values = {
        "planned_cut_feed_mm_min": CUT_FEED,
        "planned_plunge_feed_mm_min": PLUNGE_FEED,
        "recommendation_id": None,
        "depth_levels_mm": (_DEPTH,),
        "travel_height_mm": _TRAVEL,
        "clearance_mm": _TRAVEL,
        "stepdown_mm": 1.0,
        "removal_max_depth_mm": 3.0,
        "stock_allowance_mm": 0.0,
    }
    values.update(overrides)
    return RectangularPlannerOptions(**values)


def _oracle():
    """Handwritten poses for the origin rectangle. Zeros are positive."""
    z = -_DEPTH
    return (
        ("plunge", (0.0, 0.0, _TRAVEL), (0.0, 0.0, z), PLUNGE_FEED),
        ("cut", (0.0, 0.0, z), (_WIDTH, 0.0, z), CUT_FEED),
        ("cut", (_WIDTH, 0.0, z), (_WIDTH, _HEIGHT, z), CUT_FEED),
        ("cut", (_WIDTH, _HEIGHT, z), (0.0, _HEIGHT, z), CUT_FEED),
        ("cut", (0.0, _HEIGHT, z), (0.0, 0.0, z), CUT_FEED),
        ("retract", (0.0, 0.0, z), (0.0, 0.0, _TRAVEL), None),
    )


def _has_negative_zero(lines: list[Line2D]) -> bool:
    for line in lines:
        for point in (line.start, line.end):
            for value in (point.x, point.y, point.z):
                if value == 0 and math.copysign(1.0, value) < 0:
                    return True
    return False


def _assert_same_number(actual, expected, where: str) -> None:
    assert actual == expected, where
    if actual == 0 or expected == 0:
        assert math.copysign(1.0, actual) == math.copysign(1.0, expected), where
        assert math.copysign(1.0, actual) == 1.0, where


def _assert_oracle(expansion, where: str) -> None:
    motions = tuple(
        motion for path in expansion.plan.paths for motion in path.motions)
    expected = _oracle()
    assert len(motions) == len(expected), where
    for index, (row, motion) in enumerate(zip(expected, motions)):
        kind, start, end, feed = row
        place = f"{where} motion {index}"
        assert motion.kind.value == kind, place
        assert motion.planned_feed_mm_min == feed, place
        for axis, actual, wanted in (
            ("start.x", motion.start.x, start[0]),
            ("start.y", motion.start.y, start[1]),
            ("start.z", motion.start.z, start[2]),
            ("end.x", motion.end.x, end[0]),
            ("end.y", motion.end.y, end[1]),
            ("end.z", motion.end.z, end[2]),
        ):
            _assert_same_number(actual, wanted, f"{place} {axis}")
    text = toolpath_to_json(expansion.plan)
    assert "-0.0" not in text, where


def _expand_lines(lines: list[Line2D]):
    operation = make_operation_plan(
        lines, target_depth_mm=_DEPTH, with_recommendation=False)
    return expand_rectangular_contour(
        operation, operation.definitions[0].id, _options())


def test_mixed_zero_inputs_keep_a_negative_zero():
    sides = _mixed_sides()
    assert _has_negative_zero(sides)
    assert math.copysign(1.0, sides[0].start.x) == -1.0
    assert math.copysign(1.0, sides[0].start.y) == -1.0


def test_two_edge_orders_share_positive_zero_poses():
    sides = _mixed_sides()
    forward = _expand_lines(sides)
    backward = _expand_lines(list(reversed(sides)))
    _assert_oracle(forward, "forward")
    _assert_oracle(backward, "reversed")
    assert toolpath_to_json(forward.plan) != toolpath_to_json(backward.plan)


def test_every_edge_order_and_reversal_matches_the_oracle():
    sides = _mixed_sides()
    assert _has_negative_zero(sides)
    compared = 0
    for mask in range(16):
        directed = []
        for index, side in enumerate(sides):
            if mask & (1 << index):
                directed.append(Line2D(side.end, side.start))
            else:
                directed.append(side)
        for order in itertools.permutations(range(4)):
            lines = [directed[index] for index in order]
            where = f"mask {mask} order {order}"
            try:
                expansion = _expand_lines(lines)
            except PlanningError as exc:
                raise AssertionError(f"{where}: {exc.detail}") from exc
            _assert_oracle(expansion, where)
            compared += 1
    assert compared == 24 * 16


def test_tiny_nonzero_coordinates_are_not_snapped():
    tiny = 1e-9
    lines = [
        Line2D(Point(tiny, tiny, 0.0), Point(_WIDTH, tiny, 0.0)),
        Line2D(Point(_WIDTH, tiny, 0.0), Point(_WIDTH, _HEIGHT, 0.0)),
        Line2D(Point(_WIDTH, _HEIGHT, 0.0), Point(tiny, _HEIGHT, 0.0)),
        Line2D(Point(tiny, _HEIGHT, 0.0), Point(tiny, tiny, 0.0)),
    ]
    rectangle = normalize_rectangle(
        [(f"e{index}", line) for index, line in enumerate(lines)])
    assert rectangle.x_min_mm == tiny
    assert rectangle.y_min_mm == tiny
    assert rectangle.x_min_mm != 0
    assert json.dumps(rectangle.x_min_mm) == "1e-09"
    expansion = _expand_lines(lines)
    text = toolpath_to_json(expansion.plan)
    assert "1e-09" in text
    assert "-0.0" not in text
    plunge = expansion.plan.paths[0].motions[0]
    assert plunge.start.x == tiny
    assert plunge.start.y == tiny


def test_gaps_diagonals_and_nonplanar_edges_still_refuse():
    gap = [
        Line2D(Point(0.0, 0.0, 0.0), Point(_WIDTH - 1e-9, 0.0, 0.0)),
        Line2D(Point(_WIDTH, 0.0, 0.0), Point(_WIDTH, _HEIGHT, 0.0)),
        Line2D(Point(_WIDTH, _HEIGHT, 0.0), Point(0.0, _HEIGHT, 0.0)),
        Line2D(Point(0.0, _HEIGHT, 0.0), Point(0.0, 0.0, 0.0)),
    ]
    diagonal = [
        Line2D(Point(0.0, 0.0, 0.0), Point(_WIDTH, _HEIGHT, 0.0)),
        Line2D(Point(_WIDTH, 0.0, 0.0), Point(_WIDTH, _HEIGHT, 0.0)),
        Line2D(Point(_WIDTH, _HEIGHT, 0.0), Point(0.0, _HEIGHT, 0.0)),
        Line2D(Point(0.0, _HEIGHT, 0.0), Point(0.0, 0.0, 0.0)),
    ]
    raised = [
        Line2D(Point(0.0, 0.0, 1.0), Point(_WIDTH, 0.0, 1.0)),
        *_mixed_sides()[1:],
    ]
    for lines in (gap, diagonal, raised):
        operation = make_operation_plan(
            lines, target_depth_mm=_DEPTH, with_recommendation=False)
        try:
            expand_rectangular_contour(
                operation, operation.definitions[0].id, _options())
        except PlanningError as exc:
            assert exc.code == "UNSUPPORTED_CAPABILITY"
        else:
            raise AssertionError("a non-rectangle was expanded")


def test_bool_and_string_coordinates_are_not_coerced():
    sides = _mixed_sides()
    bool_edge = Line2D(Point(True, 0.0, 0.0), Point(_WIDTH, 0.0, 0.0))
    string_edge = Line2D(Point("0", 0.0, 0.0), Point(_WIDTH, 0.0, 0.0))
    for edge in (bool_edge, string_edge):
        try:
            normalize_rectangle(
                [("bad", edge), *[(f"e{i}", side) for i, side in enumerate(sides[1:], start=1)]])
        except PlanningError as exc:
            assert exc.code == "UNSUPPORTED_CAPABILITY"
        else:
            raise AssertionError("a non-numeric coordinate was accepted")


def test_source_bytes_keep_their_zero_sign_and_digest():
    negative = _mixed_sides()
    positive = [
        Line2D(
            Point(abs(line.start.x), abs(line.start.y), abs(line.start.z)),
            Point(abs(line.end.x), abs(line.end.y), abs(line.end.z)),
        )
        for line in negative
    ]
    plan_negative = make_operation_plan(
        negative, target_depth_mm=_DEPTH, with_recommendation=False)
    plan_positive = make_operation_plan(
        positive, target_depth_mm=_DEPTH, with_recommendation=False)
    text_negative = operation_plan_to_json(plan_negative, indent=2, sort_keys=True)
    text_positive = operation_plan_to_json(plan_positive, indent=2, sort_keys=True)
    assert "-0.0" in text_negative
    assert "-0.0" not in text_positive
    assert hashlib.sha256(text_negative.encode("utf-8")).hexdigest() != (
        hashlib.sha256(text_positive.encode("utf-8")).hexdigest())
    before = math.copysign(1.0, negative[0].start.x)
    _expand_lines(negative)
    _expand_lines(positive)
    assert math.copysign(1.0, negative[0].start.x) == before == -1.0
    assert "-0.0" in operation_plan_to_json(plan_negative)


def test_reordered_sources_keep_distinct_plan_digests(tmp_path):
    from cam_creation_studio.traceability.encoding import sha256_bytes
    from cam_creation_studio.traceability.planner_inputs import load_planner_inputs
    from cam_creation_studio.traceability.planning import build_generated_candidate

    def package_with(root, lines):
        write_planned_package(root)
        plan = make_operation_plan(lines)
        text = operation_plan_to_json(plan, indent=2, sort_keys=True) + "\n"
        plan_path = root / "operation_plan.json"
        plan_path.write_text(text, encoding="utf-8", newline="\n")
        planner_path = root / "planner-inputs.json"
        planner = json.loads(planner_path.read_text(encoding="utf-8"))
        planner["definition_id"] = plan.definitions[0].id
        planner["operation_plan"]["sha256"] = sha256_bytes(plan_path.read_bytes())
        planner_path.write_text(
            json.dumps(planner, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return plan_path.read_bytes()

    first_bytes = package_with(tmp_path / "first", golden_lines())
    second_bytes = package_with(tmp_path / "second", list(reversed(golden_lines())))
    assert first_bytes != second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() != hashlib.sha256(second_bytes).hexdigest()
    poses = []
    digests = []
    for root, raw in (
        (tmp_path / "first", first_bytes),
        (tmp_path / "second", second_bytes),
    ):
        verification = verify_package(root)
        loaded, refusal = load_planner_inputs(
            root, verification.bundle.snapshot.request_raw)
        assert refusal is None and loaded is not None
        candidate, refusal = build_generated_candidate(verification, loaded)
        assert refusal is None and candidate is not None
        assert (root / "operation_plan.json").read_bytes() == raw
        motions = tuple(
            motion for path in candidate.plan.paths for motion in path.motions)
        poses.append(tuple(
            (motion.kind.value, (motion.start.x, motion.start.y, motion.start.z),
             (motion.end.x, motion.end.y, motion.end.z), motion.planned_feed_mm_min)
            for motion in motions
        ))
        digests.append(candidate.plan_digest)
    assert poses[0] == poses[1]
    assert digests[0] != digests[1]


def test_cs016_strategy_fingerprints_stay_on_their_recorded_values():
    assert strategy_fingerprint(ToolpathStrategy(travel_height_mm=5.0)) == (
        "strat-515fe3fce9055a2986400477114b9fe3")
    assert strategy_fingerprint(ToolpathStrategy(
        stepdown_mm=1.5, stepover_mm=2.0, travel_height_mm=5.0)) == (
        "strat-3c2afabf15385cba86068f3504793dd1")
    assert strategy_fingerprint(ToolpathStrategy(
        stepdown_mm=1, travel_height_mm=5)) == (
        "strat-a41285012cab55cc93e78ec7e8c84d3b")


def test_explicit_motion_identity_stays_unavailable(tmp_path):
    package = build_synthetic_package(tmp_path / "coupon")
    x0, y0, x1, y1 = CENTER
    motions = []
    index = 0
    for depth in (1.0, 2.0):
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
    verification = verify_package(package)
    digest = plan_digest_for(verification, motions)
    evaluation = evaluate_explicit_motion_export(
        package, motions, fixture_review_bytes(digest), mode="offline")
    assert evaluation.allowed
    assert evaluation.manifest["planner_id"] == "unavailable"
    assert evaluation.manifest["planner_version"] == "unavailable"
    assert evaluation.manifest["motion_source"] == "explicit_linear_motion"
    assert evaluation.manifest["contract_version"] == (
        "creation-studio.traceable-export-manifest/1")


def test_verify_only_witness_does_not_plan(tmp_path):
    package = write_planned_package(tmp_path / "rectangle")
    payload = run_witness(package, tmp_path / "verify", case="rectangle")
    assert payload["reason_codes"] == ["UNSUPPORTED_CAPABILITY"]
    assert payload["program_written"] is False
    assert payload["candidate_plan"] is None
    assert not (tmp_path / "verify" / "program.gcode").exists()
