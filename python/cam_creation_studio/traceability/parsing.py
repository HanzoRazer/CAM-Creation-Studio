"""Strict parsing for traceable-planning documents.

Malformed input becomes a refusal. It does not escape as an uncaught
exception from :func:`parse_request_bytes`.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable

from . import codes
from .compatibility import (
    MAX_DOCUMENT_BYTES,
    REQUEST_FIELDS,
    REQUEST_VERSION,
    REVIEW_VERSION,
    ROLE_PROFILES,
    ROLES,
)
from .errors import TraceabilityDefect
from .models import (
    AdmissionRecord,
    ArtifactRef,
    GeometryRecord,
    PlanningRequest,
    ProposalRecord,
    Refusal,
    ReviewRecord,
    SubjectRecord,
    ValidationRecord,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class _ParseFailure(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class _DuplicateKey(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class _NonFinite(Exception):
    def __init__(self, token: str) -> None:
        super().__init__(token)
        self.token = token


def _fail(code: str, detail: str) -> None:
    raise _ParseFailure(code, detail)


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen[key] = value
    return seen


def _constant(token: str) -> None:
    raise _NonFinite(token)


def load_bounded_json(raw: bytes) -> dict:
    """Parse one JSON object. Duplicate keys and non-finite numbers are refused."""
    if not isinstance(raw, (bytes, bytearray)):
        raise TraceabilityDefect("load_bounded_json expects bytes")
    if len(raw) > MAX_DOCUMENT_BYTES:
        _fail(codes.SCHEMA_INVALID, "document exceeds the size limit")
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail(codes.SCHEMA_INVALID, "UTF-8 BOM is not accepted")
    try:
        text = bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        _fail(codes.SCHEMA_INVALID, "document is not UTF-8")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except _DuplicateKey as exc:
        _fail(codes.SCHEMA_INVALID, f"duplicate key {exc.key!r}")
    except _NonFinite as exc:
        _fail(codes.SCHEMA_INVALID, f"non-finite number {exc.token}")
    except json.JSONDecodeError as exc:
        _fail(codes.SCHEMA_INVALID, f"malformed JSON: {exc.msg}")
    except (ValueError, RecursionError):
        _fail(codes.SCHEMA_INVALID, "JSON exceeds supported numeric or nesting limits")
    if not isinstance(value, dict):
        _fail(codes.SCHEMA_INVALID, "document must be a JSON object")
    return value


def _closed(
    data: Any,
    required: tuple[str, ...],
    optional: tuple[str, ...],
    what: str,
) -> dict:
    if not isinstance(data, dict):
        _fail(codes.SCHEMA_INVALID, f"{what} must be an object")
    allowed = set(required) | set(optional)
    unknown = sorted(key for key in data if key not in allowed)
    if unknown:
        _fail(codes.SCHEMA_INVALID, f"{what} has unknown fields {unknown}")
    missing = [key for key in required if key not in data]
    if missing:
        _fail(codes.SCHEMA_INVALID, f"{what} is missing {missing}")
    return data


def _identity(value: Any, what: str) -> str:
    if isinstance(value, bool) or isinstance(value, (int, float)):
        _fail(codes.SCHEMA_INVALID, f"{what} must be a string, not a number")
    if value is None:
        _fail(codes.SCHEMA_INVALID, f"{what} must be a non-blank string")
    if not isinstance(value, str):
        _fail(codes.SCHEMA_INVALID, f"{what} must be a non-blank string")
    if value.strip() == "" or value != value.strip():
        _fail(codes.SCHEMA_INVALID, f"{what} must be a non-blank string")
    return value


def _version_string(value: Any, what: str) -> str:
    if isinstance(value, (list, dict)):
        _fail(codes.UNSUPPORTED_VERSION, f"{what} must be a version string")
    if isinstance(value, bool) or not isinstance(value, str):
        _fail(codes.UNSUPPORTED_VERSION, f"{what} must be a version string")
    if value.strip() == "":
        _fail(codes.UNSUPPORTED_VERSION, f"{what} must be a version string")
    return value


def _finite(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(codes.SCHEMA_INVALID, f"{what} must be a finite number")
    try:
        number = float(value)
    except OverflowError:
        _fail(codes.SCHEMA_INVALID, f"{what} must be a finite number")
    if not math.isfinite(number):
        _fail(codes.SCHEMA_INVALID, f"{what} must be a finite number")
    return number


def _positive(value: Any, what: str) -> float:
    number = _finite(value, what)
    if number <= 0:
        _fail(codes.SCHEMA_INVALID, f"{what} must be greater than 0")
    return number


def _non_negative(value: Any, what: str) -> float:
    number = _finite(value, what)
    if number < 0:
        _fail(codes.SCHEMA_INVALID, f"{what} must be greater than or equal to 0")
    return number


def _sha(value: Any, what: str) -> str:
    text = _identity(value, what)
    if _SHA256.fullmatch(text) is None:
        _fail(codes.SCHEMA_INVALID, f"{what} must be a lowercase SHA-256 hex digest")
    return text


def _timestamp(value: Any, what: str) -> str:
    text = _identity(value, what)
    if _TIMESTAMP.fullmatch(text) is None:
        _fail(codes.SCHEMA_INVALID, f"{what} is not a timezone-aware timestamp")
    from datetime import datetime
    iso = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(iso)
    except ValueError:
        _fail(codes.SCHEMA_INVALID, f"{what} is not a timezone-aware timestamp")
    return text


def _bool_field(value: Any, what: str) -> bool:
    if not isinstance(value, bool):
        _fail(codes.SCHEMA_INVALID, f"{what} must be a boolean")
    return value


def _contract(data: dict, what: str, expected_id: str, expected_version: str) -> None:
    contract_id = _version_string(data["contract_id"], f"{what} contract_id")
    contract_version = _version_string(
        data["contract_version"], f"{what} contract_version")
    if contract_id != expected_id or contract_version != expected_version:
        _fail(
            codes.UNSUPPORTED_VERSION,
            f"{what} profile {contract_id}/{contract_version} is not "
            f"the supported experimental profile {expected_id}/{expected_version}",
        )


def _rectangle(data: dict, prefix: str) -> tuple[float, float, float, float]:
    x_min = _finite(data["x_min_mm"], f"{prefix}.x_min_mm")
    y_min = _finite(data["y_min_mm"], f"{prefix}.y_min_mm")
    x_max = _finite(data["x_max_mm"], f"{prefix}.x_max_mm")
    y_max = _finite(data["y_max_mm"], f"{prefix}.y_max_mm")
    if x_min >= x_max or y_min >= y_max:
        _fail(codes.SCHEMA_INVALID, f"{prefix} must have a positive area")
    return x_min, y_min, x_max, y_max


def parse_request_document(data: dict) -> PlanningRequest:
    """Validate a decoded request object. Unknown fields are refused."""
    raw = _closed(data, REQUEST_FIELDS, (), "planning request")
    version = _version_string(raw["contract_version"], "contract_version")
    if version != REQUEST_VERSION:
        _fail(
            codes.UNSUPPORTED_VERSION,
            f"unsupported planning-request version {version!r}",
        )
    origin = _identity(raw["workflow_origin"], "workflow_origin")
    if origin not in ("imported", "human_authored"):
        _fail(codes.SCHEMA_INVALID, "workflow_origin is not a supported value")
    subject = _closed(raw["subject"], ("id",), (), "subject")
    geometry = _closed(raw["geometry"], ("id", "revision"), (), "geometry")
    frame = _closed(raw["coordinate_frame"], ("id", "name"), (), "coordinate_frame")
    stock = _closed(
        raw["stock"],
        ("id", "material_id", "x_mm", "y_mm", "z_mm"),
        (),
        "stock",
    )
    operation = _closed(
        raw["operation"],
        ("type", "centerline"),
        (),
        "operation",
    )
    center = _closed(
        operation["centerline"],
        ("x_min_mm", "y_min_mm", "x_max_mm", "y_max_mm"),
        (),
        "operation.centerline",
    )
    tooling = _closed(
        raw["tooling"],
        ("id", "kind", "orientation", "diameter_mm"),
        (),
        "tooling",
    )
    strategy = _closed(
        raw["strategy"],
        (
            "id",
            "depth_levels_mm",
            "travel_height_mm",
            "clearance_mm",
            "stepdown_mm",
            "stock_allowance_mm",
        ),
        (),
        "strategy",
    )
    profile = _closed(raw["machine_profile"], ("id",), (), "machine_profile")
    removal = _closed(
        raw["removal_region"],
        ("x_min_mm", "y_min_mm", "x_max_mm", "y_max_mm", "max_depth_mm"),
        (),
        "removal_region",
    )
    units = _identity(raw["units"], "units")
    operation_type = _identity(operation["type"], "operation.type")
    if operation_type != "closed_rectangular_contour":
        _fail(
            codes.UNSUPPORTED_CAPABILITY,
            f"operation type {operation_type!r} is not supported",
        )
    levels = strategy["depth_levels_mm"]
    if not isinstance(levels, list) or not levels:
        _fail(codes.SCHEMA_INVALID, "strategy.depth_levels_mm must be a non-empty list")
    parsed_levels: list[float] = []
    for index, item in enumerate(levels):
        parsed_levels.append(_positive(item, f"strategy.depth_levels_mm[{index}]"))
    for previous, current in zip(parsed_levels, parsed_levels[1:]):
        if current <= previous:
            _fail(
                codes.SCHEMA_INVALID,
                "strategy.depth_levels_mm must be strictly increasing",
            )
    artifacts = _parse_artifact_refs(raw["upstream_artifacts"])
    cx0, cy0, cx1, cy1 = _rectangle(center, "operation.centerline")
    rx0, ry0, rx1, ry1 = _rectangle(removal, "removal_region")
    if origin == "human_authored":
        _fail(
            codes.PROVENANCE_IMMUTABLE,
            "an imported artifact chain cannot be relabeled human_authored",
        )
    return PlanningRequest(
        contract_version=version,
        request_id=_identity(raw["request_id"], "request_id"),
        workflow_origin=origin,
        package_id=_identity(raw["package_id"], "package_id"),
        subject_id=_identity(subject["id"], "subject.id"),
        geometry_id=_identity(geometry["id"], "geometry.id"),
        geometry_revision=_identity(geometry["revision"], "geometry.revision"),
        units=units,
        frame_id=_identity(frame["id"], "coordinate_frame.id"),
        frame_name=_identity(frame["name"], "coordinate_frame.name"),
        stock_id=_identity(stock["id"], "stock.id"),
        material_id=_identity(stock["material_id"], "stock.material_id"),
        stock_x_mm=_positive(stock["x_mm"], "stock.x_mm"),
        stock_y_mm=_positive(stock["y_mm"], "stock.y_mm"),
        stock_z_mm=_positive(stock["z_mm"], "stock.z_mm"),
        operation_type=operation_type,
        center_x_min_mm=cx0,
        center_y_min_mm=cy0,
        center_x_max_mm=cx1,
        center_y_max_mm=cy1,
        tool_id=_identity(tooling["id"], "tooling.id"),
        tool_kind=_identity(tooling["kind"], "tooling.kind"),
        tool_orientation=_identity(tooling["orientation"], "tooling.orientation"),
        tool_diameter_mm=_positive(tooling["diameter_mm"], "tooling.diameter_mm"),
        strategy_id=_identity(strategy["id"], "strategy.id"),
        depth_levels_mm=tuple(parsed_levels),
        travel_height_mm=_finite(strategy["travel_height_mm"], "strategy.travel_height_mm"),
        clearance_mm=_positive(strategy["clearance_mm"], "strategy.clearance_mm"),
        stepdown_mm=_positive(strategy["stepdown_mm"], "strategy.stepdown_mm"),
        stock_allowance_mm=_non_negative(
            strategy["stock_allowance_mm"], "strategy.stock_allowance_mm"),
        profile_id=_identity(profile["id"], "machine_profile.id"),
        removal_x_min_mm=rx0,
        removal_y_min_mm=ry0,
        removal_x_max_mm=rx1,
        removal_y_max_mm=ry1,
        removal_max_depth_mm=_positive(
            removal["max_depth_mm"], "removal_region.max_depth_mm"),
        positional_tolerance_mm=_non_negative(
            raw["positional_tolerance_mm"], "positional_tolerance_mm"),
        artifacts=artifacts,
    )


def _parse_artifact_refs(value: Any) -> tuple[ArtifactRef, ...]:
    if not isinstance(value, list):
        _fail(codes.SCHEMA_INVALID, "upstream_artifacts must be a list")
    refs: list[ArtifactRef] = []
    for index, item in enumerate(value):
        data = _closed(
            item,
            (
                "role",
                "contract_id",
                "contract_version",
                "artifact_id",
                "package_ref",
                "sha256",
            ),
            (),
            f"upstream_artifacts[{index}]",
        )
        role = _identity(data["role"], f"upstream_artifacts[{index}].role")
        if role not in ROLES:
            _fail(codes.SCHEMA_INVALID, f"unsupported artifact role {role!r}")
        expected_id, expected_version = ROLE_PROFILES[role]
        contract_id = _version_string(
            data["contract_id"], f"upstream_artifacts[{index}].contract_id")
        contract_version = _version_string(
            data["contract_version"],
            f"upstream_artifacts[{index}].contract_version",
        )
        if (contract_id, contract_version) != (expected_id, expected_version):
            _fail(
                codes.UNSUPPORTED_VERSION,
                f"artifact role {role} profile {contract_id}/{contract_version} "
                "is not the supported experimental profile",
            )
        refs.append(ArtifactRef(
            role=role,
            contract_id=contract_id,
            contract_version=contract_version,
            artifact_id=_identity(
                data["artifact_id"], f"upstream_artifacts[{index}].artifact_id"),
            package_ref=_identity(
                data["package_ref"], f"upstream_artifacts[{index}].package_ref"),
            sha256=_sha(data["sha256"], f"upstream_artifacts[{index}].sha256"),
        ))
    seen = [ref.role for ref in refs]
    if len(seen) != len(set(seen)) or set(seen) != set(ROLES):
        _fail(
            codes.SCHEMA_INVALID,
            "upstream_artifacts must contain exactly one of each supported role",
        )
    return tuple(refs)


def parse_proposal(data: dict) -> ProposalRecord:
    raw = _closed(
        data,
        (
            "contract_id",
            "contract_version",
            "artifact_id",
            "proposal_id",
            "subject_id",
            "geometry_id",
            "geometry_revision",
            "package_id",
            "units",
            "coordinate_frame_id",
            "operation_type",
        ),
        (),
        "proposal",
    )
    expected_id, expected_version = ROLE_PROFILES["proposal"]
    _contract(raw, "proposal", expected_id, expected_version)
    return ProposalRecord(
        artifact_id=_identity(raw["artifact_id"], "proposal.artifact_id"),
        proposal_id=_identity(raw["proposal_id"], "proposal.proposal_id"),
        subject_id=_identity(raw["subject_id"], "proposal.subject_id"),
        geometry_id=_identity(raw["geometry_id"], "proposal.geometry_id"),
        geometry_revision=_identity(
            raw["geometry_revision"], "proposal.geometry_revision"),
        package_id=_identity(raw["package_id"], "proposal.package_id"),
        units=_identity(raw["units"], "proposal.units"),
        coordinate_frame_id=_identity(
            raw["coordinate_frame_id"], "proposal.coordinate_frame_id"),
        operation_type=_identity(raw["operation_type"], "proposal.operation_type"),
    )


def parse_validation(data: dict) -> ValidationRecord:
    raw = _closed(
        data,
        (
            "contract_id",
            "contract_version",
            "artifact_id",
            "validation_id",
            "proposal_id",
            "proposal_digest",
            "subject_id",
            "geometry_id",
            "geometry_revision",
            "package_id",
            "result",
        ),
        (),
        "validation",
    )
    expected_id, expected_version = ROLE_PROFILES["validation"]
    _contract(raw, "validation", expected_id, expected_version)
    return ValidationRecord(
        artifact_id=_identity(raw["artifact_id"], "validation.artifact_id"),
        validation_id=_identity(raw["validation_id"], "validation.validation_id"),
        proposal_id=_identity(raw["proposal_id"], "validation.proposal_id"),
        proposal_digest=_sha(raw["proposal_digest"], "validation.proposal_digest"),
        subject_id=_identity(raw["subject_id"], "validation.subject_id"),
        geometry_id=_identity(raw["geometry_id"], "validation.geometry_id"),
        geometry_revision=_identity(
            raw["geometry_revision"], "validation.geometry_revision"),
        package_id=_identity(raw["package_id"], "validation.package_id"),
        result=_identity(raw["result"], "validation.result"),
    )


def parse_admission(data: dict) -> AdmissionRecord:
    raw = _closed(
        data,
        (
            "contract_id",
            "contract_version",
            "artifact_id",
            "producer_id",
            "disposition",
            "proposal_id",
            "proposal_digest",
            "validation_id",
            "validation_digest",
            "subject_id",
            "geometry_id",
            "geometry_revision",
            "package_id",
            "current_state",
        ),
        (
            "advisory_allowed",
            "advisory_authority_granted",
            "approved",
            "pin_status",
        ),
        "admission",
    )
    expected_id, expected_version = ROLE_PROFILES["admission"]
    _contract(raw, "admission", expected_id, expected_version)
    disposition = _identity(raw["disposition"], "admission.disposition")
    if disposition not in (
        "admitted_for_human_review",
        "refused",
        "advisory_only",
    ):
        _fail(codes.SCHEMA_INVALID, "admission.disposition is not a supported value")
    current_state = _identity(raw["current_state"], "admission.current_state")
    if current_state != "not_established":
        _fail(
            codes.CURRENT_STATE_UNAVAILABLE,
            "admission current state cannot be established by this repository",
        )
    pin_status = None
    if "pin_status" in raw:
        pin_status = _identity(raw["pin_status"], "admission.pin_status")
    return AdmissionRecord(
        artifact_id=_identity(raw["artifact_id"], "admission.artifact_id"),
        producer_id=_identity(raw["producer_id"], "admission.producer_id"),
        disposition=disposition,
        proposal_id=_identity(raw["proposal_id"], "admission.proposal_id"),
        proposal_digest=_sha(raw["proposal_digest"], "admission.proposal_digest"),
        validation_id=_identity(raw["validation_id"], "admission.validation_id"),
        validation_digest=_sha(
            raw["validation_digest"], "admission.validation_digest"),
        subject_id=_identity(raw["subject_id"], "admission.subject_id"),
        geometry_id=_identity(raw["geometry_id"], "admission.geometry_id"),
        geometry_revision=_identity(
            raw["geometry_revision"], "admission.geometry_revision"),
        package_id=_identity(raw["package_id"], "admission.package_id"),
        current_state=current_state,
        pin_status=pin_status,
        advisory_allowed=(
            _bool_field(raw["advisory_allowed"], "admission.advisory_allowed")
            if "advisory_allowed" in raw else None
        ),
        advisory_authority_granted=(
            _bool_field(
                raw["advisory_authority_granted"],
                "admission.advisory_authority_granted",
            )
            if "advisory_authority_granted" in raw else None
        ),
        approved=(
            _bool_field(raw["approved"], "admission.approved")
            if "approved" in raw else None
        ),
    )


def parse_geometry(data: dict) -> GeometryRecord:
    raw = _closed(
        data,
        (
            "contract_id",
            "contract_version",
            "artifact_id",
            "geometry_id",
            "revision",
            "units",
            "coordinate_frame_id",
            "kind",
            "x_min_mm",
            "y_min_mm",
            "x_max_mm",
            "y_max_mm",
        ),
        (),
        "geometry",
    )
    expected_id, expected_version = ROLE_PROFILES["geometry"]
    _contract(raw, "geometry", expected_id, expected_version)
    kind = _identity(raw["kind"], "geometry.kind")
    if kind != "rectangle":
        _fail(codes.UNSUPPORTED_CAPABILITY, f"geometry kind {kind!r} is not supported")
    x_min, y_min, x_max, y_max = _rectangle(raw, "geometry")
    return GeometryRecord(
        artifact_id=_identity(raw["artifact_id"], "geometry.artifact_id"),
        geometry_id=_identity(raw["geometry_id"], "geometry.geometry_id"),
        revision=_identity(raw["revision"], "geometry.revision"),
        units=_identity(raw["units"], "geometry.units"),
        coordinate_frame_id=_identity(
            raw["coordinate_frame_id"], "geometry.coordinate_frame_id"),
        kind=kind,
        x_min_mm=x_min,
        y_min_mm=y_min,
        x_max_mm=x_max,
        y_max_mm=y_max,
    )


def parse_subject(data: dict) -> SubjectRecord:
    raw = _closed(
        data,
        (
            "contract_id",
            "contract_version",
            "artifact_id",
            "subject_id",
            "kind",
        ),
        (),
        "subject",
    )
    expected_id, expected_version = ROLE_PROFILES["subject"]
    _contract(raw, "subject", expected_id, expected_version)
    return SubjectRecord(
        artifact_id=_identity(raw["artifact_id"], "subject.artifact_id"),
        subject_id=_identity(raw["subject_id"], "subject.subject_id"),
        kind=_identity(raw["kind"], "subject.kind"),
    )


def parse_review_document(data: dict) -> ReviewRecord:
    raw = _closed(
        data,
        (
            "contract_version",
            "review_id",
            "plan_digest",
            "decision",
            "policy_digest",
            "reviewer_ref",
            "experimental",
            "authority",
        ),
        ("recorded_at",),
        "review",
    )
    version = _version_string(raw["contract_version"], "review.contract_version")
    if version != REVIEW_VERSION:
        _fail(codes.UNSUPPORTED_VERSION, f"unsupported review version {version!r}")
    decision = _identity(raw["decision"], "review.decision")
    if decision not in ("accepted", "rejected"):
        _fail(codes.SCHEMA_INVALID, "review.decision is not a supported value")
    authority = _identity(raw["authority"], "review.authority")
    recorded_at = None
    if "recorded_at" in raw:
        recorded_at = _timestamp(raw["recorded_at"], "review.recorded_at")
    return ReviewRecord(
        contract_version=version,
        review_id=_identity(raw["review_id"], "review.review_id"),
        plan_digest=_sha(raw["plan_digest"], "review.plan_digest"),
        decision=decision,
        policy_digest=_sha(raw["policy_digest"], "review.policy_digest"),
        reviewer_ref=_identity(raw["reviewer_ref"], "review.reviewer_ref"),
        experimental=_bool_field(raw["experimental"], "review.experimental"),
        authority=authority,
        recorded_at=recorded_at,
    )


def parse_request_bytes(raw: bytes) -> tuple[PlanningRequest | None, Refusal | None]:
    """Parse request bytes. Input failures return a refusal and do not raise."""
    return _capture(lambda: parse_request_document(load_bounded_json(raw)))


def parse_review_bytes(raw: bytes) -> tuple[ReviewRecord | None, Refusal | None]:
    return _capture(lambda: parse_review_document(load_bounded_json(raw)))


def _capture(fn: Callable[[], Any]) -> tuple[Any | None, Refusal | None]:
    try:
        return fn(), None
    except _ParseFailure as exc:
        return None, Refusal(exc.code, exc.detail)
