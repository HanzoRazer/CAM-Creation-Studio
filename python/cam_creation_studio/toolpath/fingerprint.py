"""Deterministic strategy and upstream fingerprints (CS-016).

Fingerprints are planning-input identity, not machine-readiness. Labels,
notes, and display names are omitted. No timestamps.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from ..geometry.models import Arc2D, Circle2D, Line2D, Polyline2D, Spline2D
from ..operations.models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationDefinition,
    OperationFeedRecommendation,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
    definition_type_name,
)
from ..shared.geometry import Point
from ..shared.ids import stable_id
from ..workspace.models import GeometryWorkspace
from .errors import ToolpathError
from .models import ToolpathStrategy


def _blob(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def strategy_fingerprint(strategy: ToolpathStrategy) -> str:
    """Computational identity of a strategy. ``label`` is omitted."""
    payload = {
        "peck_depth_mm": strategy.peck_depth_mm,
        "retract_height_mm": strategy.retract_height_mm,
        "stepdown_mm": strategy.stepdown_mm,
        "stepover_mm": strategy.stepover_mm,
        "travel_height_mm": strategy.travel_height_mm,
    }
    return stable_id(_blob(payload), prefix="strat-")


def upstream_fingerprint(
    *,
    geometry_ids: tuple[str, ...],
    geometry_digest: str,
    definition_digest: str,
    binding_id: str,
    tool_diameter_mm: float | None,
    tool_flutes: int | None,
    material_id: str,
    material_chipload_mm: tuple[float, float] | None,
    recommendation_digest: str | None,
    strategy_fingerprint: str,
    planned_feed_mm_min: float | None,
) -> str:
    """Fingerprint of inputs that make a persisted plan stale when they change."""
    chipload = (
        None if material_chipload_mm is None
        else [material_chipload_mm[0], material_chipload_mm[1]]
    )
    payload = {
        "binding_id": binding_id,
        "definition_digest": definition_digest,
        "geometry_digest": geometry_digest,
        "geometry_ids": list(geometry_ids),
        "material_chipload_mm": chipload,
        "material_id": material_id,
        "planned_feed_mm_min": planned_feed_mm_min,
        "recommendation_digest": recommendation_digest,
        "strategy_fingerprint": strategy_fingerprint,
        "tool_diameter_mm": tool_diameter_mm,
        "tool_flutes": tool_flutes,
    }
    return stable_id(_blob(payload), prefix="up-")


def definition_digest(definition: OperationDefinition) -> str:
    """Computational identity of an operation definition.

    Type, depth, relation, direction, allowances, and drill peck/retract
    intent. Display names and intent IDs are omitted.
    """
    payload: dict = {"definition_type": definition_type_name(definition)}
    if isinstance(definition, ReferenceDefinition):
        return _blob(payload)
    payload["target_depth_mm"] = definition.target_depth_mm
    if isinstance(definition, ContourDefinition):
        payload["relation"] = definition.relation.value
        payload["direction"] = definition.direction.value
        payload["stock_allowance_mm"] = definition.stock_allowance_mm
    elif isinstance(definition, PocketDefinition):
        payload["direction"] = definition.direction.value
        payload["wall_allowance_mm"] = definition.wall_allowance_mm
        payload["floor_allowance_mm"] = definition.floor_allowance_mm
    elif isinstance(definition, DrillDefinition):
        payload["retract_height_mm"] = definition.retract_height_mm
        payload["peck_depth_mm"] = definition.peck_depth_mm
    elif isinstance(definition, SlotDefinition):
        payload["relation"] = definition.relation.value
        payload["direction"] = definition.direction.value
        payload["slot_width_mm"] = definition.slot_width_mm
    elif isinstance(definition, EngraveDefinition):
        pass
    return _blob(payload)


def recommendation_digest(
    recommendation: OperationFeedRecommendation | None,
) -> str | None:
    """Recommendation id plus calculator-driving fingerprint, or ``None``."""
    if recommendation is None:
        return None
    return _blob({
        "id": recommendation.id,
        "input_fingerprint": recommendation.input_fingerprint,
    })


def geometry_digest(entries: Sequence[tuple[str, object]]) -> str:
    """Hash of referenced entity geometry (kind + millimetre coordinates).

    Layer names, DXF handles, and other display provenance are omitted.
    """
    payload = [
        {"id": geometry_id, "geometry": _entity_payload(entity)}
        for geometry_id, entity in entries
    ]
    return _blob(payload)


def geometry_digest_for_ids(
    workspace: GeometryWorkspace,
    geometry_ids: tuple[str, ...],
) -> str:
    """Digest the workspace entities named by ``geometry_ids``."""
    refs = {ref.id: ref for ref in workspace.geometry_refs}
    entries: list[tuple[str, object]] = []
    for geometry_id in geometry_ids:
        ref = refs.get(geometry_id)
        if ref is None:
            raise ToolpathError(f"unknown geometry id {geometry_id!r}")
        try:
            entity = workspace.geometry.entities[ref.entity_index]
        except IndexError as exc:
            raise ToolpathError(
                f"geometry id {geometry_id!r} has no entity"
            ) from exc
        entries.append((geometry_id, entity))
    return geometry_digest(entries)


def _entity_payload(entity: object) -> dict:
    if isinstance(entity, Line2D):
        return {
            "kind": "line",
            "start": _point(entity.start),
            "end": _point(entity.end),
        }
    if isinstance(entity, Arc2D):
        return {
            "kind": "arc",
            "center": _point(entity.center),
            "radius": entity.radius,
            "start_angle": entity.start_angle,
            "end_angle": entity.end_angle,
        }
    if isinstance(entity, Circle2D):
        return {
            "kind": "circle",
            "center": _point(entity.center),
            "radius": entity.radius,
        }
    if isinstance(entity, Polyline2D):
        return {
            "kind": "polyline",
            "closed": entity.closed,
            "vertices": [_point(p) for p in entity.vertices],
        }
    if isinstance(entity, Spline2D):
        return {
            "kind": "spline",
            "closed": entity.closed,
            "degree": entity.degree,
            "periodic": entity.periodic,
            "rational": entity.rational,
            "representation": entity.representation,
            "control_points": [_point(p) for p in entity.control_points],
            "fit_points": [_point(p) for p in entity.fit_points],
            "knots": list(entity.knots),
            "weights": list(entity.weights),
        }
    raise ToolpathError(
        f"unsupported geometry type {type(entity)!r} for digest")


def _point(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y, "z": point.z}
