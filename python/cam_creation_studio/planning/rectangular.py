"""Expand one explicit rectangular cutter centerline into linear passes.

This is not contour offsetting. The rectangle is already the cutter
centerline. Traversal starts at ``(xmin, ymin)`` and walks
``(xmax, ymin) → (xmax, ymax) → (xmin, ymax) → (xmin, ymin)`` as viewed
from +Z. That order is deterministic. It is not a climb-milling claim.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..geometry.models import Line2D
from ..operations.enums import ContourRelation, CutDirection
from ..operations.errors import BindingError
from ..operations.models import ContourDefinition
from ..operations.plan import OperationPlan
from ..operations.resolution import (
    binding_for_definition,
    resolve_material,
    resolve_tool,
)
from ..shared.geometry import Point
from ..shared.numbers import round_for_gcode
from ..toolpath.builders import (
    build_toolpath_plan,
    make_linear_motion,
    make_operation_path,
)
from ..toolpath.enums import MotionKind
from ..toolpath.errors import ToolpathError
from ..toolpath.models import ToolpathStrategy
from ..workspace.models import OperationKind
from ..workspace.refs import resolve_entity
from .errors import PlanningError
from .limits import MAX_DEPTH_LEVELS, MAX_MOTIONS, MOTIONS_PER_PASS
from .models import NormalizedRectangle, RectangularExpansion, RectangularPlannerOptions

_UNSUPPORTED = "UNSUPPORTED_CAPABILITY"
_DEPTH = "DEPTH_LIMIT_EXCEEDED"
_CLEARANCE = "CLEARANCE_VIOLATION"


def expand_rectangular_contour(
    operation_plan: OperationPlan,
    definition_id: str,
    options: RectangularPlannerOptions,
) -> RectangularExpansion:
    """Validate one contour and emit plunge / cut / retract passes.

    Resource counts are refused before any motion object is constructed.
    The limits are the module constants. This function has no parameter
    that raises them.
    """
    if not isinstance(operation_plan, OperationPlan):
        raise PlanningError(_UNSUPPORTED, "planner input is not an OperationPlan")
    if not isinstance(definition_id, str) or not definition_id.strip():
        raise PlanningError(_UNSUPPORTED, "definition_id must be a non-blank string")
    if not isinstance(options, RectangularPlannerOptions):
        raise PlanningError(_UNSUPPORTED, "planner options are missing")
    _refuse_if_over_limit(options.depth_levels_mm)
    _validate_feeds(options)
    _validate_depths(options)
    if options.travel_height_mm < options.clearance_mm:
        raise PlanningError(
            _CLEARANCE, "travel height is below the declared clearance")
    if options.stock_allowance_mm != 0:
        raise PlanningError(
            _UNSUPPORTED, "stock allowance must be exactly zero")
    definition = _require_contour(operation_plan, definition_id, options)
    rectangle = _rectangle_from_plan(operation_plan, definition)
    _require_endmill(operation_plan, definition_id)
    paths = _passes(rectangle, options)
    strategy = ToolpathStrategy(
        travel_height_mm=options.travel_height_mm,
        stepdown_mm=options.stepdown_mm,
        depth_levels_mm=options.depth_levels_mm,
    )
    try:
        plan = build_toolpath_plan(
            operation_plan,
            definition_id,
            strategy,
            tuple(paths),
            recommendation_id=options.recommendation_id,
            planned_feed_mm_min=options.planned_cut_feed_mm_min,
        )
    except ToolpathError as exc:
        raise PlanningError(_UNSUPPORTED, str(exc)) from exc
    _require_pass_continuity(plan)
    return RectangularExpansion(plan=plan, rectangle=rectangle)


def normalize_rectangle(
    edges: Sequence[tuple[str, object]],
) -> NormalizedRectangle:
    """Return the Z0 rectangle, or refuse when the edges are not one.

    ``edges`` is ``(entity_id, entity)`` in selection order. Matching is
    exact and undirected. Partial, repeated, diagonal, and non-planar
    edges refuse.
    """
    if len(edges) != 4:
        raise PlanningError(
            _UNSUPPORTED,
            f"rectangle requires exactly four edges, found {len(edges)}",
        )
    parsed: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    xs: list[float] = []
    ys: list[float] = []
    for entity_id, entity in edges:
        if not isinstance(entity_id, str) or not entity_id:
            raise PlanningError(_UNSUPPORTED, "edge id must be a non-blank string")
        if not isinstance(entity, Line2D):
            raise PlanningError(
                _UNSUPPORTED, "only straight Line2D edges are supported")
        for point in (entity.start, entity.end):
            if not all(math.isfinite(value) for value in (point.x, point.y, point.z)):
                raise PlanningError(_UNSUPPORTED, "edge coordinates must be finite")
            if point.z != 0:
                raise PlanningError(
                    _UNSUPPORTED, "rectangle is not in the Z0 plane")
        dx = entity.end.x - entity.start.x
        dy = entity.end.y - entity.start.y
        if dx == 0 and dy == 0:
            raise PlanningError(_UNSUPPORTED, "rectangle edge has zero length")
        if dx != 0 and dy != 0:
            raise PlanningError(
                _UNSUPPORTED, "rectangle edges must be axis-aligned")
        start = (entity.start.x, entity.start.y)
        end = (entity.end.x, entity.end.y)
        parsed.append((entity_id, start, end))
        xs.extend((start[0], end[0]))
        ys.extend((start[1], end[1]))
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if not (x_max > x_min and y_max > y_min):
        raise PlanningError(_UNSUPPORTED, "rectangle is degenerate")
    corners = (
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    )
    expected = {
        _undirected(corners[index], corners[(index + 1) % 4]): index
        for index in range(4)
    }
    ordered: list[str | None] = [None, None, None, None]
    for entity_id, start, end in parsed:
        slot = expected.get(_undirected(start, end))
        if slot is None:
            raise PlanningError(
                _UNSUPPORTED,
                "edges do not form one closed axis-aligned rectangle",
            )
        if ordered[slot] is not None:
            raise PlanningError(_UNSUPPORTED, "rectangle edge is repeated")
        ordered[slot] = entity_id
    if any(item is None for item in ordered):
        raise PlanningError(
            _UNSUPPORTED, "edges do not form one closed axis-aligned rectangle")
    return NormalizedRectangle(
        x_min_mm=x_min,
        y_min_mm=y_min,
        x_max_mm=x_max,
        y_max_mm=y_max,
        edge_ids=(ordered[0], ordered[1], ordered[2], ordered[3]),
    )


def _undirected(
    start: tuple[float, float], end: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    return (start, end) if start <= end else (end, start)


def _refuse_if_over_limit(levels: object) -> None:
    if isinstance(levels, (str, bytes)) or not isinstance(levels, Sequence):
        raise PlanningError(_DEPTH, "depth levels must be a sequence")
    count = len(levels)
    if count > MAX_DEPTH_LEVELS:
        raise PlanningError(
            _UNSUPPORTED,
            f"depth level count {count} exceeds the local limit "
            f"{MAX_DEPTH_LEVELS}",
        )
    motions = count * MOTIONS_PER_PASS
    if motions > MAX_MOTIONS:
        raise PlanningError(
            _UNSUPPORTED,
            f"planned motion count {motions} exceeds the local limit "
            f"{MAX_MOTIONS}",
        )


def _validate_feeds(options: RectangularPlannerOptions) -> None:
    _positive_feed("planned_cut_feed_mm_min", options.planned_cut_feed_mm_min)
    _positive_feed(
        "planned_plunge_feed_mm_min", options.planned_plunge_feed_mm_min)


def _positive_feed(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanningError(_UNSUPPORTED, f"{name} must be an explicit positive feed")
    if not math.isfinite(float(value)) or value <= 0:
        raise PlanningError(_UNSUPPORTED, f"{name} must be an explicit positive feed")
    if round_for_gcode(float(value)) <= 0:
        raise PlanningError(
            _UNSUPPORTED, f"{name} rounds to zero at posting precision")


def _validate_depths(options: RectangularPlannerOptions) -> None:
    if isinstance(options.stepdown_mm, bool) or not isinstance(
        options.stepdown_mm, (int, float)
    ):
        raise PlanningError(_DEPTH, "stepdown must be a positive number")
    if not math.isfinite(float(options.stepdown_mm)) or options.stepdown_mm <= 0:
        raise PlanningError(_DEPTH, "stepdown must be a positive number")
    if isinstance(options.removal_max_depth_mm, bool) or not isinstance(
        options.removal_max_depth_mm, (int, float)
    ):
        raise PlanningError(_DEPTH, "removal max depth must be a finite number")
    if not math.isfinite(float(options.removal_max_depth_mm)):
        raise PlanningError(_DEPTH, "removal max depth must be a finite number")
    if isinstance(options.travel_height_mm, bool) or not isinstance(
        options.travel_height_mm, (int, float)
    ) or isinstance(options.clearance_mm, bool) or not isinstance(
        options.clearance_mm, (int, float)
    ):
        raise PlanningError(_CLEARANCE, "travel height and clearance must be finite")
    if not math.isfinite(float(options.travel_height_mm)) or not math.isfinite(
        float(options.clearance_mm)
    ):
        raise PlanningError(_CLEARANCE, "travel height and clearance must be finite")
    previous = 0.0
    for index, level in enumerate(options.depth_levels_mm):
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise PlanningError(_DEPTH, f"depth level {index} is not a finite number")
        if not math.isfinite(float(level)) or level <= 0:
            raise PlanningError(
                _DEPTH, f"depth level {index} must be positive and finite")
        if level <= previous:
            raise PlanningError(
                _DEPTH, "depth levels must be strictly increasing")
        if level - previous > options.stepdown_mm:
            raise PlanningError(
                _DEPTH, "a depth step exceeds the declared stepdown")
        if level > options.removal_max_depth_mm:
            raise PlanningError(
                _DEPTH,
                f"depth level {level} mm exceeds declared removal limit "
                f"{options.removal_max_depth_mm} mm",
            )
        previous = float(level)


def _require_contour(
    operation_plan: OperationPlan,
    definition_id: str,
    options: RectangularPlannerOptions,
) -> ContourDefinition:
    definitions = operation_plan.definitions
    if len(definitions) != 1 or definitions[0].id != definition_id:
        raise PlanningError(
            _UNSUPPORTED, "the planner accepts exactly one contour definition")
    definition = definitions[0]
    if not isinstance(definition, ContourDefinition):
        raise PlanningError(_UNSUPPORTED, "definition is not a contour")
    if definition.relation is not ContourRelation.ON:
        raise PlanningError(
            _UNSUPPORTED, "only an on-path contour relation is supported")
    if definition.direction is not CutDirection.UNSPECIFIED:
        raise PlanningError(
            _UNSUPPORTED,
            "an explicit climb or conventional direction is refused",
        )
    if definition.stock_allowance_mm != 0 or options.stock_allowance_mm != 0:
        raise PlanningError(_UNSUPPORTED, "stock allowance must be exactly zero")
    if not options.depth_levels_mm:
        raise PlanningError(_DEPTH, "depth levels are empty")
    if definition.target_depth_mm != options.depth_levels_mm[-1]:
        raise PlanningError(
            _DEPTH, "the final depth level is not the definition target depth")
    workspace = operation_plan.workspace
    if len(workspace.operations) != 1 or len(workspace.selections) != 1:
        raise PlanningError(
            _UNSUPPORTED, "the planner accepts one selection and one operation")
    intent = workspace.operations[0]
    if intent.kind is not OperationKind.CONTOUR or intent.id != definition.intent_id:
        raise PlanningError(
            _UNSUPPORTED, "the contour intent does not match the definition")
    if len(operation_plan.bindings) != 1:
        raise PlanningError(_UNSUPPORTED, "the planner accepts exactly one binding")
    if len(operation_plan.recommendations) > 1:
        raise PlanningError(
            _UNSUPPORTED, "the planner accepts at most one stored recommendation")
    return definition


def _rectangle_from_plan(
    operation_plan: OperationPlan, definition: ContourDefinition,
) -> NormalizedRectangle:
    workspace = operation_plan.workspace
    intent = workspace.operations[0]
    selection = workspace.selections[0]
    if selection.id != intent.selection_id:
        raise PlanningError(_UNSUPPORTED, "the selection does not match the intent")
    try:
        edges = tuple(
            (entity_id, resolve_entity(workspace, entity_id))
            for entity_id in selection.entity_ids
        )
    except Exception as exc:
        raise PlanningError(_UNSUPPORTED, str(exc)) from exc
    return normalize_rectangle(edges)


def _require_endmill(operation_plan: OperationPlan, definition_id: str) -> None:
    binding = binding_for_definition(operation_plan, definition_id)
    if binding is None:
        raise PlanningError(_UNSUPPORTED, "definition has no binding")
    try:
        tool = resolve_tool(binding)
        resolve_material(binding)
    except BindingError as exc:
        raise PlanningError(_UNSUPPORTED, str(exc)) from exc
    if tool.kind != "endmill" or tool.flutes is None or tool.diameter_mm <= 0:
        raise PlanningError(
            _UNSUPPORTED, "rectangular planner requires a flat end mill binding")


def _passes(rectangle: NormalizedRectangle, options: RectangularPlannerOptions):
    x0 = rectangle.x_min_mm
    y0 = rectangle.y_min_mm
    x1 = rectangle.x_max_mm
    y1 = rectangle.y_max_mm
    travel = options.travel_height_mm
    corners = (
        (x1, y0, rectangle.edge_ids[0]),
        (x1, y1, rectangle.edge_ids[1]),
        (x0, y1, rectangle.edge_ids[2]),
        (x0, y0, rectangle.edge_ids[3]),
    )
    paths = []
    index = 0
    for depth in options.depth_levels_mm:
        z = -float(depth)
        motions = []
        motions.append(make_linear_motion(
            MotionKind.PLUNGE,
            Point(x0, y0, travel),
            Point(x0, y0, z),
            index=index,
            planned_feed_mm_min=options.planned_plunge_feed_mm_min,
        ))
        index += 1
        previous = Point(x0, y0, z)
        for corner_x, corner_y, edge_id in corners:
            end = Point(corner_x, corner_y, z)
            motions.append(make_linear_motion(
                MotionKind.CUT,
                previous,
                end,
                index=index,
                planned_feed_mm_min=options.planned_cut_feed_mm_min,
                geometry_ids=(edge_id,),
            ))
            index += 1
            previous = end
        motions.append(make_linear_motion(
            MotionKind.RETRACT,
            previous,
            Point(x0, y0, travel),
            index=index,
        ))
        index += 1
        paths.append(make_operation_path(
            motions, existing_count=len(paths), depth_mm=depth))
    return paths


def _require_pass_continuity(plan) -> None:
    previous = None
    for path in plan.paths:
        for motion in path.motions:
            if motion.start == motion.end:
                raise PlanningError(_UNSUPPORTED, "planner emitted a zero-length move")
            if previous is not None and motion.start != previous:
                raise PlanningError(
                    _UNSUPPORTED, "planner emitted a discontinuous pass")
            previous = motion.end
