"""Consumer-owned compatibility policy for traceable planning.

Upstream proposal, validation, and admission schemas are not ratified in this
repository. Nothing here invents a canonical upstream version. Every pin is
experimental. An artifact field such as ``pin_status`` or ``approved`` cannot
change that.

There is no operational trust anchor. A rectangular centerline planner
covers one explicit rectangle. Operational governed export stays disabled.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..planning.limits import (
    GENERATED_MANIFEST_VERSION,
    GENERATED_PLAN_VERSION,
    INPUT_VERSION,
    MAX_DEPTH_LEVELS,
    MAX_MOTIONS,
    MAX_PLANNER_INPUT_BYTES,
    MOTION_SOURCE as RECTANGULAR_MOTION_SOURCE,
    PLANNER_ID as RECTANGULAR_PLANNER_ID,
    RECTANGULAR_CENTERLINE_AVAILABLE,
)
from .codes import REASON_CODES
from .encoding import digest_json

REQUEST_VERSION = "creation-studio.traceable-planning-request/1"
PLAN_VERSION = "creation-studio.traceable-plan/1"
MANIFEST_VERSION = "creation-studio.traceable-export-manifest/1"
REVIEW_VERSION = "creation-studio.plan-review/1"
POLICY_ID = "creation-studio.traceable-planning-policy/1"

FIXTURE_VERSION = "fixture-1"
PROPOSAL_CONTRACT = "experimental.cam-assist.proposal"
VALIDATION_CONTRACT = "experimental.cam-assist.validation"
ADMISSION_CONTRACT = "experimental.cam-assist.admission"
GEOMETRY_CONTRACT = "experimental.creation-studio.geometry"
SUBJECT_CONTRACT = "experimental.creation-studio.subject"

FIXTURE_PRODUCER = "synthetic-fixture-producer"
SUPPORTED_PROFILE = "synthetic-router-mm"
SUPPORTED_FRAME = "stock-fixed-coupon-xy"
SUPPORTED_OPERATION = "closed_rectangular_contour"
SUPPORTED_UNITS = "mm"

# Local policy. Not readable from an artifact or a CLI flag.
OPERATIONAL_GOVERNED_EXPORT = False
OPERATIONAL_TRUST_CONFIGURED = False
CONTOUR_PLANNER_AVAILABLE = False

PLANNER_ID = "unavailable"
PLANNER_VERSION = "unavailable"
POSTPROCESSOR_ID = "cam_creation_studio.gcode.generator"

EXPERIMENTAL_BANNER = "EXPERIMENTAL — NOT FOR MACHINING"

ROLES: tuple[str, ...] = (
    "proposal",
    "validation",
    "admission",
    "geometry",
    "subject",
)

ROLE_PROFILES: dict[str, tuple[str, str]] = {
    "proposal": (PROPOSAL_CONTRACT, FIXTURE_VERSION),
    "validation": (VALIDATION_CONTRACT, FIXTURE_VERSION),
    "admission": (ADMISSION_CONTRACT, FIXTURE_VERSION),
    "geometry": (GEOMETRY_CONTRACT, FIXTURE_VERSION),
    "subject": (SUBJECT_CONTRACT, FIXTURE_VERSION),
}

MAX_DOCUMENT_BYTES = 256 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024

# Numerical identity only, not additional permitted removal. Hard removal
# bounds remain exact. Relative tolerance is deliberately disabled.
DEPTH_LEVEL_ABS_TOLERANCE_MM = 1e-9

REQUEST_FIELDS: tuple[str, ...] = (
    "contract_version",
    "request_id",
    "workflow_origin",
    "package_id",
    "subject",
    "geometry",
    "units",
    "coordinate_frame",
    "stock",
    "operation",
    "tooling",
    "strategy",
    "machine_profile",
    "removal_region",
    "positional_tolerance_mm",
    "upstream_artifacts",
)

AUTHORITY_LIMITATIONS: tuple[str, ...] = (
    EXPERIMENTAL_BANNER,
    "Does not establish acoustic validity.",
    "Does not authorize physical machining.",
    "Does not claim machine readiness, full collision simulation, "
    "structural safety, or cutting-force analysis.",
    "A rectangular cutter-centerline planner expands one explicit rectangle. "
    "It does not offset geometry. Explicit linear motion is not planner output. "
    "Numerically zero rectangle coordinates are positive zero, and generated "
    "candidate metadata is re-derived from captured inputs.",
    "A fixture review tests binding only and is not human approval.",
    "Admission to human review is not plan approval.",
    "Operational governed export is disabled.",
)


@dataclass(frozen=True, slots=True)
class ProfileLimit:
    """What the local witness is willing to check. Not a machine certificate."""

    profile_id: str
    units: str
    tool_kinds: tuple[str, ...]
    orientations: tuple[str, ...]
    linear_only: bool
    experimental: bool


SUPPORTED_PROFILES: dict[str, ProfileLimit] = {
    SUPPORTED_PROFILE: ProfileLimit(
        profile_id=SUPPORTED_PROFILE,
        units=SUPPORTED_UNITS,
        tool_kinds=("flat_end_mill",),
        orientations=("fixed",),
        linear_only=True,
        experimental=True,
    ),
}


def postprocessor_version() -> str:
    """Source package version. Stable for a given tree, not a certified post."""
    from cam_creation_studio import __version__
    return __version__


def assigned_maturity(pin_status: str | None = None) -> str:
    """Maturity is local. ``pin_status`` is accepted and ignored."""
    del pin_status
    return "experimental"


def policy_document() -> dict:
    """The local policy payload. Its digest is what a review must bind."""
    from ..planning import limits as rectangle_limits

    return {
        "policy_id": POLICY_ID,
        "operational_governed_export": OPERATIONAL_GOVERNED_EXPORT,
        "operational_trust_configured": OPERATIONAL_TRUST_CONFIGURED,
        "contour_planner_available": CONTOUR_PLANNER_AVAILABLE,
        "planner_id": PLANNER_ID,
        "planner_version": PLANNER_VERSION,
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "fixture_producers": [FIXTURE_PRODUCER],
        "supported_operation": SUPPORTED_OPERATION,
        "supported_frame": SUPPORTED_FRAME,
        "supported_profile": SUPPORTED_PROFILE,
        "supported_units": SUPPORTED_UNITS,
        "depth_level_abs_tolerance_mm": DEPTH_LEVEL_ABS_TOLERANCE_MM,
        "rectangular_centerline_available": RECTANGULAR_CENTERLINE_AVAILABLE,
        "rectangular_planner_id": RECTANGULAR_PLANNER_ID,
        "rectangular_planner_version": rectangle_limits.PLANNER_VERSION,
        "rectangular_motion_source": RECTANGULAR_MOTION_SOURCE,
        "rectangular_input_version": INPUT_VERSION,
        "generated_plan_version": GENERATED_PLAN_VERSION,
        "generated_manifest_version": GENERATED_MANIFEST_VERSION,
        "max_rectangular_depth_levels": MAX_DEPTH_LEVELS,
        "max_rectangular_motions": MAX_MOTIONS,
        "max_planner_input_bytes": MAX_PLANNER_INPUT_BYTES,
        "profiles": {
            role: {"contract_id": pair[0], "contract_version": pair[1],
                   "maturity": "experimental"}
            for role, pair in sorted(ROLE_PROFILES.items())
        },
        "reason_codes": list(REASON_CODES),
        "authority_limitations": list(AUTHORITY_LIMITATIONS),
    }


def policy_digest() -> str:
    """Digest of :func:`policy_document`. Volatile timestamps are absent."""
    return digest_json(policy_document())
