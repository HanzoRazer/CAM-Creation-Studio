"""Strict intake for rectangular planner inputs.

The five upstream artifacts stay on ``TraceablePlanningRequestV1``. This
module reads a separate closed document and the operation plan it names.
Operation plans are decoded with the existing serializer after strict JSON
parsing. There is no second operation-plan representation.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from ..operations.errors import (
    BindingError,
    OperationDefinitionError,
    RecommendationError,
)
from ..operations.models import ContourDefinition
from ..operations.plan import OperationPlan
from ..operations.resolution import (
    binding_for_definition,
    resolve_material,
    resolve_tool,
)
from ..operations.serialization import operation_plan_from_dict
from ..planning.errors import PlanningError
from ..planning.limits import INPUT_VERSION, MAX_PLANNER_INPUT_BYTES
from ..planning.rectangular import normalize_rectangle
from ..workspace.errors import WorkspaceError
from ..workspace.refs import resolve_entity
from . import codes
from .artifacts import read_bounded, resolve_package_ref
from .encoding import sha256_bytes
from .models import AdditionalInputSnapshot, PlanningRequest, Refusal
from .parsing import _ParseFailure, load_bounded_json

_SHA = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = (
    "contract_version",
    "request_sha256",
    "operation_plan",
    "definition_id",
    "planned_cut_feed_mm_min",
    "planned_plunge_feed_mm_min",
    "recommendation_id",
)
_PLAN_FIELDS = ("package_ref", "sha256")
_PLANNER_INPUT_REF = "planner-inputs.json"


@dataclass(frozen=True, slots=True)
class PlannerInputDocument:
    """Parsed ``rectangular_planner_input/1`` document."""

    contract_version: str
    request_sha256: str
    operation_plan_ref: str
    operation_plan_sha256: str
    definition_id: str
    planned_cut_feed_mm_min: float
    planned_plunge_feed_mm_min: float
    recommendation_id: str | None


@dataclass(frozen=True, slots=True)
class LoadedPlannerInputs:
    """Document, exact bytes, and the decoded operation plan."""

    document: PlannerInputDocument
    additional: AdditionalInputSnapshot
    operation_plan: OperationPlan


def load_planner_inputs(
    package_root: Path,
    request_raw: bytes,
) -> tuple[LoadedPlannerInputs | None, Refusal | None]:
    """Read ``planner-inputs.json`` and the operation plan it names."""
    path, refusal = resolve_package_ref(package_root, _PLANNER_INPUT_REF)
    if refusal is not None or path is None:
        return None, refusal
    raw, refusal = read_bounded(path, MAX_PLANNER_INPUT_BYTES)
    if refusal is not None or raw is None:
        return None, refusal
    document, refusal = parse_planner_input_bytes(raw)
    if refusal is not None or document is None:
        return None, refusal
    if document.request_sha256 != sha256_bytes(request_raw):
        return None, Refusal(
            codes.DIGEST_MISMATCH,
            "planner input request_sha256 does not match the stored request",
        )
    plan_path, refusal = resolve_package_ref(
        package_root, document.operation_plan_ref)
    if refusal is not None or plan_path is None:
        return None, refusal
    plan_raw, refusal = read_bounded(plan_path, MAX_PLANNER_INPUT_BYTES)
    if refusal is not None or plan_raw is None:
        return None, refusal
    if sha256_bytes(plan_raw) != document.operation_plan_sha256:
        return None, Refusal(
            codes.DIGEST_MISMATCH,
            "operation-plan bytes do not match the planner input digest",
        )
    operation_plan, refusal = decode_operation_plan(plan_raw)
    if refusal is not None or operation_plan is None:
        return None, refusal
    additional = AdditionalInputSnapshot(
        planner_input_ref=_PLANNER_INPUT_REF,
        planner_input_raw=bytes(raw),
        planner_input_sha256=sha256_bytes(raw),
        operation_plan_ref=document.operation_plan_ref,
        operation_plan_raw=bytes(plan_raw),
        operation_plan_sha256=sha256_bytes(plan_raw),
    )
    return LoadedPlannerInputs(document, additional, operation_plan), None


def parse_planner_input_bytes(
    raw: bytes,
) -> tuple[PlannerInputDocument | None, Refusal | None]:
    """Parse one planner-input document. Unknown fields refuse."""
    try:
        document = load_bounded_json(raw)
    except _ParseFailure as exc:
        return None, Refusal(exc.code, exc.detail)
    extra = [key for key in document if key not in _FIELDS]
    missing = [key for key in _FIELDS if key not in document]
    if extra or missing:
        return None, Refusal(
            codes.SCHEMA_INVALID, "planner input fields are not the closed set")
    version = document["contract_version"]
    if not isinstance(version, str):
        return None, Refusal(
            codes.UNSUPPORTED_VERSION, "planner input version is not a string")
    if version != INPUT_VERSION:
        return None, Refusal(
            codes.UNSUPPORTED_VERSION,
            f"unsupported planner input version {version!r}",
        )
    request_sha = document["request_sha256"]
    if not isinstance(request_sha, str) or _SHA.fullmatch(request_sha) is None:
        return None, Refusal(
            codes.SCHEMA_INVALID, "request_sha256 must be a lowercase SHA-256")
    plan = document["operation_plan"]
    if not isinstance(plan, dict):
        return None, Refusal(
            codes.SCHEMA_INVALID, "operation_plan must be an object")
    plan_extra = [key for key in plan if key not in _PLAN_FIELDS]
    plan_missing = [key for key in _PLAN_FIELDS if key not in plan]
    if plan_extra or plan_missing:
        return None, Refusal(
            codes.SCHEMA_INVALID, "operation_plan reference fields are not closed")
    package_ref = plan["package_ref"]
    plan_sha = plan["sha256"]
    if not isinstance(package_ref, str) or not package_ref.strip():
        return None, Refusal(
            codes.SCHEMA_INVALID, "operation_plan.package_ref must be a string")
    if not isinstance(plan_sha, str) or _SHA.fullmatch(plan_sha) is None:
        return None, Refusal(
            codes.SCHEMA_INVALID, "operation_plan.sha256 must be a lowercase SHA-256")
    definition_id = document["definition_id"]
    if not isinstance(definition_id, str) or not definition_id.strip():
        return None, Refusal(
            codes.SCHEMA_INVALID, "definition_id must be a non-blank string")
    try:
        cut = _feed(document["planned_cut_feed_mm_min"], "planned_cut_feed_mm_min")
        plunge = _feed(
            document["planned_plunge_feed_mm_min"], "planned_plunge_feed_mm_min")
    except _ParseFailure as exc:
        return None, Refusal(exc.code, exc.detail)
    recommendation = document["recommendation_id"]
    if recommendation is not None and (
        not isinstance(recommendation, str) or not recommendation.strip()
    ):
        return None, Refusal(
            codes.SCHEMA_INVALID,
            "recommendation_id must be null or a non-blank string",
        )
    return PlannerInputDocument(
        contract_version=version,
        request_sha256=request_sha,
        operation_plan_ref=package_ref,
        operation_plan_sha256=plan_sha,
        definition_id=definition_id,
        planned_cut_feed_mm_min=cut,
        planned_plunge_feed_mm_min=plunge,
        recommendation_id=recommendation,
    ), None


def decode_operation_plan(
    raw: bytes,
) -> tuple[OperationPlan | None, Refusal | None]:
    """Strict JSON, then the existing operation-plan serializer."""
    try:
        document = load_bounded_json(raw)
        plan = operation_plan_from_dict(document)
    except _ParseFailure as exc:
        return None, Refusal(exc.code, exc.detail)
    except (
        OperationDefinitionError, BindingError, RecommendationError,
        WorkspaceError, ValueError, TypeError, KeyError, OverflowError,
    ) as exc:
        return None, Refusal(codes.SCHEMA_INVALID, f"operation plan: {exc}")
    return plan, None


def agree_with_request(
    request: PlanningRequest,
    geometry_bounds: tuple[float, float, float, float],
    loaded: LoadedPlannerInputs,
) -> Refusal | None:
    """The operation rectangle, tool, material, and strategy must match."""
    plan = loaded.operation_plan
    document = loaded.document
    if len(plan.definitions) != 1 or plan.definitions[0].id != document.definition_id:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "planner definition does not match the operation plan",
        )
    definition = plan.definitions[0]
    if not isinstance(definition, ContourDefinition):
        return Refusal(codes.UNSUPPORTED_CAPABILITY, "definition is not a contour")
    if definition.target_depth_mm != request.depth_levels_mm[-1]:
        return Refusal(
            codes.DEPTH_LIMIT_EXCEEDED,
            "definition target depth does not match the verified request",
        )
    if definition.stock_allowance_mm != request.stock_allowance_mm:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "definition stock allowance does not match the verified request",
        )
    workspace = plan.workspace
    if len(workspace.selections) != 1 or len(workspace.operations) != 1:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "the operation plan is outside the one-rectangle case",
        )
    selection = workspace.selections[0]
    try:
        edges = tuple(
            (entity_id, resolve_entity(workspace, entity_id))
            for entity_id in selection.entity_ids
        )
        rectangle = normalize_rectangle(edges)
    except PlanningError as exc:
        return Refusal(exc.code, exc.detail)
    bounds = (
        rectangle.x_min_mm, rectangle.y_min_mm,
        rectangle.x_max_mm, rectangle.y_max_mm,
    )
    request_bounds = (
        request.center_x_min_mm, request.center_y_min_mm,
        request.center_x_max_mm, request.center_y_max_mm,
    )
    if bounds != request_bounds or bounds != geometry_bounds:
        return Refusal(
            codes.GEOMETRY_REVISION_MISMATCH,
            "selected rectangle does not match the verified geometry",
        )
    binding = binding_for_definition(plan, document.definition_id)
    if binding is None:
        return Refusal(codes.UNSUPPORTED_CAPABILITY, "definition has no binding")
    try:
        tool = resolve_tool(binding)
        material = resolve_material(binding)
    except BindingError as exc:
        return Refusal(codes.UNSUPPORTED_CAPABILITY, str(exc))
    if (
        binding.tool_id != request.tool_id
        or tool.id != request.tool_id
        or tool.diameter_mm != request.tool_diameter_mm
        or tool.kind != "endmill"
        or request.tool_kind != "flat_end_mill"
        or request.tool_orientation != "fixed"
    ):
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "resolved tool does not match the verified request",
        )
    if binding.material_id != request.material_id or material.id != request.material_id:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "resolved material does not match the verified request",
        )
    if document.recommendation_id is not None:
        stored = plan.recommendations
        if len(stored) != 1 or stored[0].id != document.recommendation_id:
            return Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                "recommendation_id is not the stored recommendation",
            )
        if stored[0].definition_id != document.definition_id:
            return Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                "recommendation does not belong to the selected definition",
            )
    return None


def _feed(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ParseFailure(codes.SCHEMA_INVALID, f"{name} must be a number")
    try:
        number = float(value)
    except OverflowError:
        raise _ParseFailure(
            codes.SCHEMA_INVALID, f"{name} must be a finite number") from None
    if not math.isfinite(number) or number <= 0:
        raise _ParseFailure(
            codes.UNSUPPORTED_CAPABILITY, f"{name} must be an explicit positive feed")
    return value
