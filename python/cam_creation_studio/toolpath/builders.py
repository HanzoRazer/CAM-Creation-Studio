"""Contract builders for controller-neutral planned motion (CS-016).

These helpers assign deterministic IDs, compute analytic arc fields, and
assemble a validated ``ToolpathPlan``. They accept already-constructed
paths. They do not offset contours, clear pockets, or expand drills.
"""

from __future__ import annotations

import math

from ..operations.errors import BindingError
from ..operations.models import ReferenceDefinition
from ..operations.plan import OperationPlan
from ..operations.recommendations import recommendation_for_definition
from ..operations.resolution import (
    binding_for_definition,
    require_definition,
    resolve_material,
    resolve_tool,
)
from ..shared.geometry import Point
from .enums import MotionKind
from .errors import ToolpathError
from .fingerprint import (
    definition_digest,
    geometry_digest_for_ids,
    recommendation_digest,
    strategy_fingerprint,
    upstream_fingerprint,
)
from .ids import make_motion_id, make_operation_path_id, make_toolpath_id
from .models import (
    TOOLPATH_PLAN_V1,
    ArcMotion,
    LinearMotion,
    MotionSegment,
    OperationPath,
    ToolpathPlan,
    ToolpathStrategy,
)
from .validation import signed_sweep, validate_toolpath_plan


def make_linear_motion(
    kind: MotionKind | str,
    start: Point,
    end: Point,
    *,
    index: int,
    planned_feed_mm_min: float | None = None,
    geometry_ids: tuple[str, ...] = (),
    id: str | None = None,
) -> LinearMotion:
    """Build one explicit pose-to-pose linear motion."""
    motion_kind = _kind(kind)
    ident = id if id is not None else make_motion_id(
        "linear", motion_kind.value, start, end, index=index)
    if not ident:
        raise ToolpathError("motion ID must not be empty")
    return LinearMotion(
        id=ident,
        kind=motion_kind,
        start=start,
        end=end,
        planned_feed_mm_min=planned_feed_mm_min,
        geometry_ids=geometry_ids,
    )


def make_arc_motion(
    start: Point,
    end: Point,
    center: Point,
    clockwise: bool,
    *,
    index: int,
    kind: MotionKind | str = MotionKind.CUT,
    planned_feed_mm_min: float | None = None,
    geometry_ids: tuple[str, ...] = (),
    id: str | None = None,
) -> ArcMotion:
    """Build one analytic XY arc. Radius and sweep are computed from geometry."""
    motion_kind = _kind(kind)
    radius = math.hypot(start.x - center.x, start.y - center.y)
    sweep = signed_sweep(start, end, center, clockwise)
    ident = id if id is not None else make_motion_id(
        "arc", motion_kind.value, start, end, index=index,
        center=center, clockwise=clockwise)
    if not ident:
        raise ToolpathError("motion ID must not be empty")
    return ArcMotion(
        id=ident,
        kind=motion_kind,
        start=start,
        end=end,
        center=center,
        radius=radius,
        clockwise=clockwise,
        sweep_rad=sweep,
        planned_feed_mm_min=planned_feed_mm_min,
        geometry_ids=geometry_ids,
    )


def make_operation_path(
    motions: tuple[MotionSegment, ...] | list[MotionSegment],
    *,
    existing_count: int = 0,
    depth_mm: float | None = None,
    id: str | None = None,
) -> OperationPath:
    """Build one ordered path. Continuity is checked at plan validation."""
    packed = tuple(motions)
    ident = id if id is not None else make_operation_path_id(
        *(m.id for m in packed), existing_count=existing_count)
    if not ident:
        raise ToolpathError("operation path ID must not be empty")
    return OperationPath(id=ident, motions=packed, depth_mm=depth_mm)


def make_toolpath_plan(
    *,
    operation_definition_id: str,
    geometry_ids: tuple[str, ...],
    binding_id: str,
    strategy: ToolpathStrategy,
    paths: tuple[OperationPath, ...],
    geometry_digest: str,
    definition_digest: str,
    recommendation_digest: str | None = None,
    recommendation_id: str | None = None,
    planned_feed_mm_min: float | None = None,
    tool_diameter_mm: float | None = None,
    tool_flutes: int | None = None,
    material_id: str = "",
    material_chipload_mm: tuple[float, float] | None = None,
    id: str | None = None,
    existing_count: int = 0,
) -> ToolpathPlan:
    """Assemble a validated plan from explicit lineage inputs and paths.

    Does not generate machining geometry.
    """
    strat_fp = strategy_fingerprint(strategy)
    up_fp = upstream_fingerprint(
        geometry_ids=geometry_ids,
        geometry_digest=geometry_digest,
        definition_digest=definition_digest,
        binding_id=binding_id,
        tool_diameter_mm=tool_diameter_mm,
        tool_flutes=tool_flutes,
        material_id=material_id,
        material_chipload_mm=material_chipload_mm,
        recommendation_digest=recommendation_digest,
        strategy_fingerprint=strat_fp,
        planned_feed_mm_min=planned_feed_mm_min,
    )
    ident = id if id is not None else make_toolpath_id(
        operation_definition_id,
        binding_id,
        strat_fp,
        *geometry_ids,
        recommendation_id=recommendation_id,
        planned_feed_mm_min=planned_feed_mm_min,
        path_ids=tuple(path.id for path in paths),
        existing_count=existing_count,
    )
    if not ident:
        raise ToolpathError("toolpath plan ID must not be empty")
    plan = ToolpathPlan(
        id=ident,
        version=TOOLPATH_PLAN_V1,
        operation_definition_id=operation_definition_id,
        geometry_ids=geometry_ids,
        binding_id=binding_id,
        strategy_fingerprint=strat_fp,
        upstream_fingerprint=up_fp,
        paths=paths,
        recommendation_id=recommendation_id,
        planned_feed_mm_min=planned_feed_mm_min,
    )
    validate_toolpath_plan(plan)
    return plan


def build_toolpath_plan(
    operation_plan: OperationPlan,
    definition_id: str,
    strategy: ToolpathStrategy,
    paths: tuple[OperationPath, ...],
    *,
    planned_feed_mm_min: float | None = None,
    id: str | None = None,
    existing_count: int = 0,
) -> ToolpathPlan:
    """Wire lineage from an ``OperationPlan`` onto already-constructed paths.

    Does not generate contour, pocket, or drill geometry. ``REFERENCE``
    definitions cannot produce a machining plan.
    """
    try:
        definition = require_definition(operation_plan, definition_id)
    except BindingError as exc:
        raise ToolpathError(str(exc)) from exc
    if isinstance(definition, ReferenceDefinition):
        raise ToolpathError(
            f"REFERENCE definition {definition_id!r} does not generate paths")
    binding = binding_for_definition(operation_plan, definition_id)
    if binding is None:
        raise ToolpathError(
            f"definition {definition_id!r} has no binding")
    intent = None
    for item in operation_plan.workspace.operations:
        if item.id == definition.intent_id:
            intent = item
            break
    if intent is None:
        raise ToolpathError(
            f"unknown operation intent {definition.intent_id!r}")
    selection = None
    for item in operation_plan.workspace.selections:
        if item.id == intent.selection_id:
            selection = item
            break
    if selection is None:
        raise ToolpathError(
            f"unknown selection {intent.selection_id!r}")
    geometry_ids = selection.entity_ids
    try:
        tool = resolve_tool(binding)
        material = resolve_material(binding)
    except BindingError as exc:
        raise ToolpathError(str(exc)) from exc
    stored = recommendation_for_definition(operation_plan, definition_id)
    return make_toolpath_plan(
        operation_definition_id=definition.id,
        geometry_ids=geometry_ids,
        binding_id=binding.id,
        strategy=strategy,
        paths=paths,
        geometry_digest=geometry_digest_for_ids(
            operation_plan.workspace, geometry_ids),
        definition_digest=definition_digest(definition),
        recommendation_digest=recommendation_digest(stored),
        recommendation_id=None if stored is None else stored.id,
        planned_feed_mm_min=planned_feed_mm_min,
        tool_diameter_mm=tool.diameter_mm,
        tool_flutes=tool.flutes,
        material_id=material.id,
        material_chipload_mm=material.chipload_mm,
        id=id,
        existing_count=existing_count,
    )


def _kind(value: MotionKind | str) -> MotionKind:
    if isinstance(value, MotionKind):
        return value
    try:
        return MotionKind(value)
    except ValueError as exc:
        raise ToolpathError(f"unknown motion kind {value!r}") from exc
