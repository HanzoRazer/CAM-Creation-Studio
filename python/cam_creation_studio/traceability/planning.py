"""Request fingerprints and the contour-planner adapter.

The adapter does not invent cutter motion. No contour planner is implemented
in this repository (CS-017 is unissued), so candidate planning refuses with
``UNSUPPORTED_CAPABILITY``.
"""

from __future__ import annotations

from ..toolpath.fingerprint import strategy_fingerprint
from ..toolpath.models import ToolpathStrategy
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
from .encoding import digest_json
from .models import PlanningRequest, Refusal, VerificationResult


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
    """Ask the contour planner for motion. It is not available."""
    del verification
    if CONTOUR_PLANNER_AVAILABLE:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "contour planner flag is set but no planner implementation exists",
        )
    return Refusal(
        codes.UNSUPPORTED_CAPABILITY,
        "contour planner is not implemented; CS-017 is unissued; "
        "no candidate toolpath is produced",
    )
