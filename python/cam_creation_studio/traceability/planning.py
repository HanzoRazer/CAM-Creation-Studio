"""Request fingerprints and the rectangular-planner adapter.

Verification-only planning still refuses. A generated candidate is built
only from planner inputs through ``cam_creation_studio.planning``. Caller
text such as ``motion_source`` is not accepted as proof of that path.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..planning import limits as rectangle_limits
from ..planning.errors import PlanningError
from ..planning.models import RectangularPlannerOptions
from ..planning.rectangular import expand_rectangular_contour
from ..toolpath.fingerprint import strategy_fingerprint
from ..toolpath.models import ToolpathPlan, ToolpathStrategy
from ..toolpath.serialization import toolpath_to_json
from . import codes
from .compatibility import (
    CONTOUR_PLANNER_AVAILABLE,
    PLANNER_ID,
    PLANNER_VERSION,
    PLAN_VERSION,
    POSTPROCESSOR_ID,
    policy_digest,
    postprocessor_version,
)
from .encoding import digest_json, sha256_bytes
from .errors import TraceabilityDefect
from .models import (
    GeneratedCandidate,
    PlanningRequest,
    Refusal,
    VerificationResult,
)
from .planner_inputs import LoadedPlannerInputs, agree_with_request
from .posting import toolpath_digest


def request_canonical(request: PlanningRequest) -> dict:
    """Deterministic request payload. No timestamps."""
    artifacts = [
        {
            "artifact_id": ref.artifact_id,
            "contract_id": ref.contract_id,
            "contract_version": ref.contract_version,
            "package_ref": ref.package_ref,
            "role": ref.role,
            "sha256": ref.sha256,
        }
        for ref in sorted(request.artifacts, key=lambda item: item.role)
    ]
    return {
        "artifacts": artifacts,
        "clearance_mm": request.clearance_mm,
        "contract_version": request.contract_version,
        "depth_levels_mm": list(request.depth_levels_mm),
        "frame_id": request.frame_id,
        "frame_name": request.frame_name,
        "geometry_id": request.geometry_id,
        "geometry_revision": request.geometry_revision,
        "material_id": request.material_id,
        "operation_type": request.operation_type,
        "package_id": request.package_id,
        "positional_tolerance_mm": request.positional_tolerance_mm,
        "profile_id": request.profile_id,
        "removal_max_depth_mm": request.removal_max_depth_mm,
        "removal_x_max_mm": request.removal_x_max_mm,
        "removal_x_min_mm": request.removal_x_min_mm,
        "removal_y_max_mm": request.removal_y_max_mm,
        "removal_y_min_mm": request.removal_y_min_mm,
        "request_id": request.request_id,
        "stepdown_mm": request.stepdown_mm,
        "strategy_id": request.strategy_id,
        "stock_allowance_mm": request.stock_allowance_mm,
        "stock_id": request.stock_id,
        "stock_x_mm": request.stock_x_mm,
        "stock_y_mm": request.stock_y_mm,
        "stock_z_mm": request.stock_z_mm,
        "subject_id": request.subject_id,
        "tool_diameter_mm": request.tool_diameter_mm,
        "tool_id": request.tool_id,
        "tool_kind": request.tool_kind,
        "tool_orientation": request.tool_orientation,
        "travel_height_mm": request.travel_height_mm,
        "units": request.units,
        "workflow_origin": request.workflow_origin,
        "center_x_max_mm": request.center_x_max_mm,
        "center_x_min_mm": request.center_x_min_mm,
        "center_y_max_mm": request.center_y_max_mm,
        "center_y_min_mm": request.center_y_min_mm,
    }


def request_digest(request: PlanningRequest) -> str:
    return digest_json(request_canonical(request))


def traceable_strategy_fingerprint(request: PlanningRequest) -> str:
    """Strategy identity, including depth levels, clearance, and allowance."""
    base = strategy_fingerprint(ToolpathStrategy(
        travel_height_mm=request.travel_height_mm,
        stepdown_mm=request.stepdown_mm,
        depth_levels_mm=request.depth_levels_mm,
    ))
    return digest_json({
        "clearance_mm": request.clearance_mm,
        "stock_allowance_mm": request.stock_allowance_mm,
        "toolpath_strategy_fingerprint": base,
    })


def compute_plan_digest(
    *,
    request_digest_value: str,
    artifact_digests: dict[str, str],
    strategy_fp: str,
    tool_diameter_mm: float,
    stock_allowance_mm: float,
    stock_id: str,
    frame_id: str,
    units: str,
    profile_id: str,
    toolpath_digest: str,
    motion_source: str,
) -> str:
    """Digest of a candidate plan. Volatile timestamps are not inputs."""
    return digest_json({
        "artifact_digests": artifact_digests,
        "contract_version": PLAN_VERSION,
        "frame_id": frame_id,
        "motion_source": motion_source,
        "planner_id": PLANNER_ID,
        "planner_version": PLANNER_VERSION,
        "policy_digest": policy_digest(),
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "profile_id": profile_id,
        "request_digest": request_digest_value,
        "stock_allowance_mm": stock_allowance_mm,
        "stock_id": stock_id,
        "strategy_fingerprint": strategy_fp,
        "tool_diameter_mm": tool_diameter_mm,
        "toolpath_digest": toolpath_digest,
        "units": units,
    })


def plan_candidate(verification: VerificationResult) -> Refusal:
    """Verification-only boundary. Planner inputs are not consulted."""
    del verification
    if CONTOUR_PLANNER_AVAILABLE:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "contour planner flag is set but no general contour planner exists",
        )
    return Refusal(
        codes.UNSUPPORTED_CAPABILITY,
        "verification-only witness does not run the rectangular planner; "
        "no candidate toolpath is produced",
    )


_GENERATION_SEAL = object()
_EXPLICIT_SEAL = object()


@dataclass(frozen=True, slots=True)
class ExplicitMotionCandidate:
    """Caller-supplied linear motion. Not rectangular-planner output."""

    source_seal: object
    motions: tuple
    plan_digest: str


def tag_explicit_motion(motions, plan_digest: str) -> ExplicitMotionCandidate:
    """Mark caller-supplied motion. Installing a planner does not relabel it."""
    return ExplicitMotionCandidate(_EXPLICIT_SEAL, tuple(motions), plan_digest)


def is_explicit(candidate: object) -> bool:
    return (
        isinstance(candidate, ExplicitMotionCandidate)
        and candidate.source_seal is _EXPLICIT_SEAL
    )


def is_generated(candidate: object) -> bool:
    return (
        isinstance(candidate, GeneratedCandidate)
        and candidate.source_seal is _GENERATION_SEAL
    )


def plan_motions(plan: ToolpathPlan) -> tuple:
    """Motions in path order. This is the order the bounds checker sees."""
    return tuple(motion for path in plan.paths for motion in path.motions)


def build_generated_candidate(
    verification: VerificationResult,
    loaded: LoadedPlannerInputs,
) -> tuple[GeneratedCandidate | None, Refusal | None]:
    """Expand one verified rectangle. The seal is set only here."""
    if not rectangle_limits.RECTANGULAR_CENTERLINE_AVAILABLE:
        return None, Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "rectangular centerline planner is not enabled by local policy",
        )
    if (
        not verification.accepted
        or verification.request is None
        or verification.bundle is None
    ):
        return None, verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified")
    request = verification.request
    geometry = verification.bundle.geometry
    refusal = agree_with_request(
        request,
        (
            geometry.x_min_mm, geometry.y_min_mm,
            geometry.x_max_mm, geometry.y_max_mm,
        ),
        loaded,
    )
    if refusal is not None:
        return None, refusal
    document = loaded.document
    options = RectangularPlannerOptions(
        planned_cut_feed_mm_min=document.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=document.planned_plunge_feed_mm_min,
        recommendation_id=document.recommendation_id,
        depth_levels_mm=request.depth_levels_mm,
        travel_height_mm=request.travel_height_mm,
        clearance_mm=request.clearance_mm,
        stepdown_mm=request.stepdown_mm,
        removal_max_depth_mm=request.removal_max_depth_mm,
        stock_allowance_mm=request.stock_allowance_mm,
    )
    try:
        expansion = expand_rectangular_contour(
            loaded.operation_plan, document.definition_id, options)
    except PlanningError as exc:
        if exc.code not in codes.REASON_CODES:
            return None, Refusal(
                codes.UNSUPPORTED_CAPABILITY, exc.detail)
        return None, Refusal(exc.code, exc.detail)
    plan = expansion.plan
    binding = loaded.operation_plan.bindings[0]
    from ..operations.resolution import resolve_material, resolve_tool
    tool = resolve_tool(binding)
    material = resolve_material(binding)
    digest = compute_generated_plan_digest(
        verification=verification,
        planner_input_sha256=loaded.additional.planner_input_sha256,
        operation_plan_sha256=loaded.additional.operation_plan_sha256,
        plan=plan,
        definition_id=document.definition_id,
        binding_id=plan.binding_id,
        geometry_ids=plan.geometry_ids,
        recommendation_id=plan.recommendation_id,
        planned_cut_feed_mm_min=document.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=document.planned_plunge_feed_mm_min,
        tool_id=tool.id,
        tool_diameter_mm=tool.diameter_mm,
        tool_flutes=tool.flutes,
        material_id=material.id,
    )
    return GeneratedCandidate(
        source_seal=_GENERATION_SEAL,
        verification=verification,
        additional=loaded.additional,
        definition_id=document.definition_id,
        planned_cut_feed_mm_min=document.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=document.planned_plunge_feed_mm_min,
        recommendation_id=plan.recommendation_id,
        binding_id=plan.binding_id,
        geometry_ids=plan.geometry_ids,
        tool_id=tool.id,
        tool_diameter_mm=tool.diameter_mm,
        tool_flutes=tool.flutes,
        material_id=material.id,
        plan=plan,
        plan_digest=digest,
    ), None


def replan_matches(candidate: GeneratedCandidate) -> Refusal | None:
    """Expand the captured operation plan again and require the same bytes."""
    from .planner_inputs import decode_operation_plan

    if not is_generated(candidate) or candidate.verification.request is None:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "caller motion_source is not generated provenance",
        )
    operation_plan, refusal = decode_operation_plan(
        candidate.additional.operation_plan_raw)
    if refusal is not None or operation_plan is None:
        return refusal
    request = candidate.verification.request
    options = RectangularPlannerOptions(
        planned_cut_feed_mm_min=candidate.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=candidate.planned_plunge_feed_mm_min,
        recommendation_id=candidate.recommendation_id,
        depth_levels_mm=request.depth_levels_mm,
        travel_height_mm=request.travel_height_mm,
        clearance_mm=request.clearance_mm,
        stepdown_mm=request.stepdown_mm,
        removal_max_depth_mm=request.removal_max_depth_mm,
        stock_allowance_mm=request.stock_allowance_mm,
    )
    try:
        expansion = expand_rectangular_contour(
            operation_plan, candidate.definition_id, options)
    except PlanningError as exc:
        return Refusal(
            exc.code if exc.code in codes.REASON_CODES else codes.UNSUPPORTED_CAPABILITY,
            exc.detail,
        )
    if toolpath_to_json(expansion.plan) != toolpath_to_json(candidate.plan):
        return Refusal(
            codes.PLAN_CHANGED,
            "regenerated rectangular plan does not match the candidate",
        )
    digest = compute_generated_plan_digest(
        verification=candidate.verification,
        planner_input_sha256=candidate.additional.planner_input_sha256,
        operation_plan_sha256=candidate.additional.operation_plan_sha256,
        plan=expansion.plan,
        definition_id=candidate.definition_id,
        binding_id=candidate.binding_id,
        geometry_ids=candidate.geometry_ids,
        recommendation_id=candidate.recommendation_id,
        planned_cut_feed_mm_min=candidate.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=candidate.planned_plunge_feed_mm_min,
        tool_id=candidate.tool_id,
        tool_diameter_mm=candidate.tool_diameter_mm,
        tool_flutes=candidate.tool_flutes,
        material_id=candidate.material_id,
    )
    if digest != candidate.plan_digest:
        return Refusal(
            codes.PLAN_CHANGED, "generated plan digest does not match its inputs")
    return None


def compute_generated_plan_digest(
    *,
    verification: VerificationResult,
    planner_input_sha256: str,
    operation_plan_sha256: str,
    plan: ToolpathPlan,
    definition_id: str,
    binding_id: str,
    geometry_ids: tuple[str, ...],
    recommendation_id: str | None,
    planned_cut_feed_mm_min: float,
    planned_plunge_feed_mm_min: float,
    tool_id: str,
    tool_diameter_mm: float,
    tool_flutes: int | None,
    material_id: str,
) -> str:
    """Digest of one generated rectangular plan. Timestamps are absent."""
    request = verification.request
    bundle = verification.bundle
    if request is None or bundle is None:
        raise TraceabilityDefect(
            "generated digest requires a verified request and bundle")
    toolpath_json = toolpath_to_json(plan)
    return digest_json({
        "artifact_digests": {
            item.role: item.sha256 for item in bundle.snapshot.artifacts
        },
        "binding_id": binding_id,
        "contract_version": rectangle_limits.GENERATED_PLAN_VERSION,
        "definition_id": definition_id,
        "frame_id": request.frame_id,
        "geometry_ids": list(geometry_ids),
        "local_limits": {
            "max_depth_levels": rectangle_limits.MAX_DEPTH_LEVELS,
            "max_motions": rectangle_limits.MAX_MOTIONS,
            "max_planner_input_bytes": rectangle_limits.MAX_PLANNER_INPUT_BYTES,
        },
        "material_id": material_id,
        "motion_source": rectangle_limits.MOTION_SOURCE,
        "operation_plan_sha256": operation_plan_sha256,
        "planned_cut_feed_mm_min": planned_cut_feed_mm_min,
        "planned_plunge_feed_mm_min": planned_plunge_feed_mm_min,
        "planner_id": rectangle_limits.PLANNER_ID,
        "planner_input_sha256": planner_input_sha256,
        "planner_version": rectangle_limits.PLANNER_VERSION,
        "policy_digest": policy_digest(),
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "profile_id": request.profile_id,
        "recommendation_id": recommendation_id,
        "request_digest": request_digest(request),
        "request_sha256": bundle.snapshot.request_sha256,
        "stock_allowance_mm": request.stock_allowance_mm,
        "strategy_fingerprint": plan.strategy_fingerprint,
        "tool_diameter_mm": tool_diameter_mm,
        "tool_flutes": tool_flutes,
        "tool_id": tool_id,
        "toolpath_digest": toolpath_digest(plan_motions(plan)),
        "toolpath_sha256": sha256_bytes(toolpath_json.encode("utf-8")),
        "units": request.units,
    })
