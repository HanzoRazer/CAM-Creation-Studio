"""Studio-owned traceable-planning records.

These types are Creation Studio planning contracts. They do not replace an
upstream proposal or admission schema.
"""

from __future__ import annotations

from dataclasses import dataclass

from .codes import REASON_CODES
from .errors import TraceabilityDefect


@dataclass(frozen=True, slots=True)
class Refusal:
    """A stable reason code plus a separate human-readable detail."""

    code: str
    detail: str

    def __post_init__(self) -> None:
        if self.code not in REASON_CODES:
            raise TraceabilityDefect(
                f"refusing with unknown reason code {self.code!r}")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise TraceabilityDefect("refusal detail must be non-blank")

    def as_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Pointer to exact stored bytes inside one package."""

    role: str
    contract_id: str
    contract_version: str
    artifact_id: str
    package_ref: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    """Parsed ``TraceablePlanningRequestV1``."""

    contract_version: str
    request_id: str
    workflow_origin: str
    package_id: str
    subject_id: str
    geometry_id: str
    geometry_revision: str
    units: str
    frame_id: str
    frame_name: str
    stock_id: str
    material_id: str
    stock_x_mm: float
    stock_y_mm: float
    stock_z_mm: float
    operation_type: str
    center_x_min_mm: float
    center_y_min_mm: float
    center_x_max_mm: float
    center_y_max_mm: float
    tool_id: str
    tool_kind: str
    tool_orientation: str
    tool_diameter_mm: float
    strategy_id: str
    depth_levels_mm: tuple[float, ...]
    travel_height_mm: float
    clearance_mm: float
    stepdown_mm: float
    stock_allowance_mm: float
    profile_id: str
    removal_x_min_mm: float
    removal_y_min_mm: float
    removal_x_max_mm: float
    removal_y_max_mm: float
    removal_max_depth_mm: float
    positional_tolerance_mm: float
    artifacts: tuple[ArtifactRef, ...]


@dataclass(frozen=True, slots=True)
class ProposalRecord:
    artifact_id: str
    proposal_id: str
    subject_id: str
    geometry_id: str
    geometry_revision: str
    package_id: str
    units: str
    coordinate_frame_id: str
    operation_type: str


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    artifact_id: str
    validation_id: str
    proposal_id: str
    proposal_digest: str
    subject_id: str
    geometry_id: str
    geometry_revision: str
    package_id: str
    result: str


@dataclass(frozen=True, slots=True)
class AdmissionRecord:
    artifact_id: str
    producer_id: str
    disposition: str
    proposal_id: str
    proposal_digest: str
    validation_id: str
    validation_digest: str
    subject_id: str
    geometry_id: str
    geometry_revision: str
    package_id: str
    current_state: str
    pin_status: str | None
    advisory_allowed: bool | None
    advisory_authority_granted: bool | None
    approved: bool | None


@dataclass(frozen=True, slots=True)
class GeometryRecord:
    artifact_id: str
    geometry_id: str
    revision: str
    units: str
    coordinate_frame_id: str
    kind: str
    x_min_mm: float
    y_min_mm: float
    x_max_mm: float
    y_max_mm: float


@dataclass(frozen=True, slots=True)
class SubjectRecord:
    artifact_id: str
    subject_id: str
    kind: str


@dataclass(frozen=True, slots=True)
class StoredBytes:
    role: str
    package_ref: str
    sha256: str
    raw: bytes


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    """Immutable bytes captured during verification."""

    package_root: str
    request_raw: bytes
    request_sha256: str
    artifacts: tuple[StoredBytes, ...]

    def by_role(self, role: str) -> StoredBytes:
        for item in self.artifacts:
            if item.role == role:
                return item
        raise TraceabilityDefect(f"snapshot is missing role {role!r}")


@dataclass(frozen=True, slots=True)
class PackageBundle:
    request: PlanningRequest
    snapshot: ArtifactSnapshot
    proposal: ProposalRecord
    validation: ValidationRecord
    admission: AdmissionRecord
    geometry: GeometryRecord
    subject: SubjectRecord


@dataclass(frozen=True, slots=True)
class VerifiedImportContext:
    """Local view of a package that survived structural and identity checks."""

    request_digest: str
    artifact_digests: tuple[tuple[str, str], ...]
    compatibility_policy_digest: str
    maturity: str
    admission_disposition: str
    producer_id: str
    trust: str
    subject_id: str
    geometry_id: str
    geometry_revision: str
    package_id: str
    proposal_id: str
    frame_id: str
    units: str
    profile_id: str
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerificationResult:
    accepted: bool
    refusal: Refusal | None
    request: PlanningRequest | None
    bundle: PackageBundle | None
    context: VerifiedImportContext | None


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    contract_version: str
    review_id: str
    plan_digest: str
    decision: str
    policy_digest: str
    reviewer_ref: str
    experimental: bool
    authority: str
    recorded_at: str | None


@dataclass(frozen=True, slots=True)
class ExportEvaluation:
    allowed: bool
    refusal: Refusal | None
    program_text: str | None
    program_sha256: str | None
    manifest: dict | None
    plan_digest: str | None
    input_manifest: dict | None


@dataclass(frozen=True, slots=True)
class AdditionalInputSnapshot:
    """Exact planner-input and operation-plan bytes captured with a candidate."""

    planner_input_ref: str
    planner_input_raw: bytes
    planner_input_sha256: str
    operation_plan_ref: str
    operation_plan_raw: bytes
    operation_plan_sha256: str


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    """A rectangular plan produced by the construction path.

    ``source_seal`` is assigned only by that path. A caller-supplied
    ``motion_source`` string is not a field on this record.
    """

    source_seal: object
    verification: VerificationResult
    additional: AdditionalInputSnapshot
    definition_id: str
    planned_cut_feed_mm_min: float
    planned_plunge_feed_mm_min: float
    recommendation_id: str | None
    binding_id: str
    geometry_ids: tuple[str, ...]
    tool_id: str
    tool_diameter_mm: float
    tool_flutes: int | None
    material_id: str
    plan: object
    plan_digest: str
