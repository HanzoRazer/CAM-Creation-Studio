"""Shared traceable-planning gate.

Parsing, resolution, identity, trust, manufacturing checks, review binding,
and governed export decisions all live here. The witness CLI and
``camstudio generate`` call this module. They do not keep a second copy of
the rules.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..planning import limits as rectangle_limits
from ..toolpath.models import MotionSegment, ToolpathPlan
from ..toolpath.preview_adapter import toolpath_to_preview
from ..toolpath.serialization import toolpath_to_dict, toolpath_to_json
from . import codes
from .artifacts import (
    load_package,
    read_bounded,
    read_exact,
    resolve_package_ref,
    reverify_additional,
    reverify_snapshot,
)
from .bounds import check_declared_request, check_motions, check_posting_precision
from .compatibility import (
    AUTHORITY_LIMITATIONS,
    EXPERIMENTAL_BANNER,
    MANIFEST_VERSION,
    PLANNER_ID,
    PLANNER_VERSION,
    PLAN_VERSION,
    POSTPROCESSOR_ID,
    assigned_maturity,
    policy_digest,
    postprocessor_version,
)
from .encoding import sha256_bytes
from .errors import TraceabilityDefect
from .identity import check_identity
from .models import (
    ExportEvaluation,
    GeneratedCandidate,
    PackageBundle,
    PlanningRequest,
    Refusal,
    ReviewRecord,
    VerificationResult,
    VerifiedImportContext,
)
from .parsing import (
    _ParseFailure,
    load_bounded_json,
    parse_request_bytes,
    parse_review_bytes,
)
from .planning import (
    build_generated_candidate,
    compute_plan_digest,
    is_explicit,
    is_generated,
    plan_candidate,
    plan_motions,
    replan_matches,
    request_digest,
    tag_explicit_motion,
    traceable_strategy_fingerprint,
)
from .planner_inputs import load_planner_inputs
from .posting import render_experimental_program, toolpath_digest
from .review import bind_review
from .trust import assess_producer

_MARKERS = (
    "upstream_artifacts",
    "traceable_planning",
    "traceable_plan",
    "traceability",
)
_MOTION_SOURCE_EXPLICIT = "explicit_linear_motion"
_ADMISSION_KEYS = (
    "contract_id", "contract_version", "proposal_id", "proposal_digest",
    "disposition", "producer_id", "advisory_authority_granted", "approved",
)
# A duplicate of any of these could hide a governed marker behind a later value.
_CLASSIFYING_KEYS = frozenset(
    ("workflow_origin", "config", "job", "admission") + _MARKERS + _ADMISSION_KEYS)


def load_generate_document(raw: bytes) -> object:
    """Parse a ``camstudio generate`` document.

    Governed documents must pass ``load_bounded_json``. An ordinary job that
    fails only those limits (size, duplicate keys, non-finite numbers) is
    parsed as it was before CS-PEP-001. That fallback is refused when the
    lenient parse looks governed or a classifying key is duplicated, so a
    second value cannot erase a provenance marker.
    """
    try:
        return load_bounded_json(raw)
    except _ParseFailure as exc:
        strict = exc
    duplicated: set[str] = set()

    def pairs(items: list[tuple[str, object]]) -> dict:
        seen: dict[str, object] = {}
        for key, value in items:
            if key in seen:
                duplicated.add(key)
            seen[key] = value
        return seen

    try:
        document = json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=pairs)
    except (ValueError, RecursionError):
        raise strict from None
    if duplicated & _CLASSIFYING_KEYS or classify_generate_document(document) != "ordinary":
        raise strict
    return document


def classify_generate_document(document: object) -> str:
    """Classify a ``camstudio generate`` document.

    Returns ``ordinary``, ``governed``, or ``provenance_stripped``.
    """
    if not isinstance(document, dict):
        return "ordinary"
    origins = _origins(document)
    imported = any(origin == "imported" for origin in origins)
    human = any(origin == "human_authored" for origin in origins)
    marked = _has_marker(document)
    if human and (imported or marked):
        return "provenance_stripped"
    if imported or marked:
        return "governed"
    return "ordinary"


def evaluate_governed_generate(document: object) -> ExportEvaluation:
    """Operational generate path for a governed document. Never writes a program."""
    kind = classify_generate_document(document)
    if kind == "ordinary":
        return ExportEvaluation(
            False, None, None, None, None, None, None)
    if kind == "provenance_stripped":
        refusal = Refusal(
            codes.PROVENANCE_IMMUTABLE,
            "imported provenance cannot be discarded by relabeling the job",
        )
        return _refused(refusal)
    refusal = Refusal(
        codes.EXPERIMENTAL_ONLY,
        "operational governed export is disabled; camstudio generate is not "
        "the offline witness path, and an admission or authority flag is not "
        "plan approval",
    )
    return _refused(refusal)


def verify_package(
    package_root: Path, *, mode: str = "offline",
) -> VerificationResult:
    """Verify one on-disk package. Input failures return a refusal."""
    if mode not in ("offline", "operational"):
        return _rejected(Refusal(
            codes.POLICY_UNSUPPORTED, f"unknown verification mode {mode!r}"))
    path, refusal = resolve_package_ref(package_root, "request.json")
    if refusal is not None or path is None:
        return _rejected(refusal or Refusal(
            codes.REFERENCE_UNRESOLVED, "request.json was not resolved"))
    raw, refusal = read_exact(path)
    if refusal is not None or raw is None:
        return _rejected(refusal or Refusal(
            codes.REFERENCE_UNRESOLVED, "request.json is unreadable"))
    request, refusal = parse_request_bytes(raw)
    if refusal is not None or request is None:
        return _rejected(refusal or Refusal(
            codes.SCHEMA_INVALID, "request did not parse"))
    snapshot, parsed, refusal = load_package(package_root, request.artifacts, raw)
    if refusal is not None or snapshot is None or parsed is None:
        return VerificationResult(False, refusal, request, None, None)
    bundle = PackageBundle(
        request=request,
        snapshot=snapshot,
        proposal=parsed["proposal"],
        validation=parsed["validation"],
        admission=parsed["admission"],
        geometry=parsed["geometry"],
        subject=parsed["subject"],
    )
    refusal = check_identity(bundle)
    if refusal is not None:
        return VerificationResult(False, refusal, request, bundle, None)
    trust, refusal = assess_producer(bundle.admission, mode=mode)
    if refusal is not None or trust is None:
        return VerificationResult(False, refusal, request, bundle, None)
    context = _context(bundle, trust)
    refusal = check_declared_request(request)
    if refusal is not None:
        return VerificationResult(False, refusal, request, bundle, context)
    return VerificationResult(True, None, request, bundle, context)


def export_governed_package(package_root: Path) -> ExportEvaluation:
    """Operational export entry. Experimental packages are refused.

    A package that verifies only as an offline fixture is refused with
    ``EXPERIMENTAL_ONLY``. Incoming authority fields cannot change that.
    """
    verification = verify_package(package_root, mode="offline")
    if not verification.accepted:
        return _refused(verification.refusal or Refusal(
            codes.UNTRUSTED_ADMISSION, "package was not verified"), verification)
    return _refused(Refusal(
        codes.EXPERIMENTAL_ONLY,
        "operational governed export is disabled for an experimental package",
    ), verification)


def evaluate_explicit_motion_export(
    package_root: Path,
    motions: tuple[MotionSegment, ...] | list[MotionSegment],
    review_bytes: bytes | None,
    *,
    mode: str,
) -> ExportEvaluation:
    """Verify a package and run the shared gate on caller-supplied motion.

    The motion is not contour-planner output. Offline mode may return a
    marked experimental program when every check passes. Operational mode
    does not.
    """
    verification = verify_package(package_root, mode="offline")
    return evaluate_verified_motion_export(
        verification, package_root, motions, review_bytes, mode=mode)


def evaluate_verified_motion_export(
    verification: VerificationResult,
    package_root: Path,
    motions: tuple[MotionSegment, ...] | list[MotionSegment],
    review_bytes: bytes | None,
    *,
    mode: str,
) -> ExportEvaluation:
    """Continue from a captured verification snapshot.

    Bytes that change after that snapshot refuse with ``SNAPSHOT_CHANGED``
    and do not produce a program. Caller-supplied motion stays explicit.
    """
    if not verification.accepted or verification.request is None or verification.bundle is None or verification.context is None:
        return _refused(verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified"), verification)
    candidate = tag_explicit_motion(motions, plan_digest="")
    return _export_source_candidate(
        verification, package_root, candidate, review_bytes, mode=mode)


def evaluate_generated_candidate_export(
    candidate: object,
    package_root: Path,
    review_bytes: bytes | None,
    *,
    mode: str,
) -> ExportEvaluation:
    """Export one sealed generated candidate. A source string is not proof."""
    if not is_generated(candidate):
        verification = getattr(candidate, "verification", None)
        if not isinstance(verification, VerificationResult):
            verification = None
        return _refused(Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "caller motion_source is not generated provenance",
        ), verification)
    return _export_source_candidate(
        candidate.verification, package_root, candidate, review_bytes, mode=mode)


def _export_source_candidate(
    verification: VerificationResult,
    package_root: Path,
    candidate: object,
    review_bytes: bytes | None,
    *,
    mode: str,
) -> ExportEvaluation:
    """Shared review and render gate for explicit and generated motion."""
    if verification.request is None or verification.bundle is None:
        return _refused(verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified"), verification)
    generated = is_generated(candidate)
    if is_explicit(candidate):
        motions = candidate.motions
    elif generated:
        motions = plan_motions(candidate.plan)
    else:
        return _refused(Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            "caller motion_source is not generated provenance",
        ), verification)
    refusal = reverify_snapshot(verification.bundle.snapshot, package_root)
    if refusal is not None:
        return _refused(refusal, verification)
    if generated:
        refusal = reverify_additional(candidate.additional, package_root)
        if refusal is not None:
            return _refused(refusal, verification)
        refusal = replan_matches(candidate)
        if refusal is not None:
            return _refused(refusal, verification, candidate.plan_digest)
    refusal = check_motions(verification.request, motions)
    if refusal is not None:
        return _refused(refusal, verification)
    refusal = check_posting_precision(verification.request, motions)
    if refusal is not None:
        return _refused(refusal, verification)
    plan_fp = candidate.plan_digest if generated else _plan_digest(verification, motions)
    review, refusal = _load_review(review_bytes)
    if refusal is not None:
        return _refused(refusal, verification)
    refusal = bind_review(review, plan_fp)
    if refusal is not None:
        return _refused(refusal, verification, plan_fp)
    if mode == "operational":
        return _refused(Refusal(
            codes.EXPERIMENTAL_ONLY,
            "an experimental package cannot be promoted to operational "
            "export by pin_status, approved, or a fixture review",
        ), verification, plan_fp)
    if mode != "offline":
        return _refused(Refusal(
            codes.POLICY_UNSUPPORTED, f"unknown export mode {mode!r}"),
            verification, plan_fp)
    if review is None:
        raise TraceabilityDefect("export passed review binding without a review")
    program, refusal = render_experimental_program(
        motions, clearance_mm=verification.request.clearance_mm)
    if refusal is not None or program is None:
        return _refused(refusal or Refusal(
            codes.UNSUPPORTED_CAPABILITY, "program was not rendered"),
            verification, plan_fp)
    program_sha = sha256_bytes(program.encode("utf-8"))
    if generated:
        manifest = _generated_manifest(
            candidate, plan_digest_value=plan_fp, program_sha=program_sha, review=review)
    else:
        manifest = _manifest(
            verification, plan_digest_value=plan_fp, program_sha=program_sha, review=review)
    return ExportEvaluation(
        allowed=True,
        refusal=None,
        program_text=program,
        program_sha256=program_sha,
        manifest=manifest,
        plan_digest=plan_fp,
        input_manifest=_input_manifest(verification),
    )


def write_offline_export(destination: Path, evaluation: ExportEvaluation) -> None:
    """Write an experimental program only when the shared gate allowed it."""
    destination.mkdir(parents=True, exist_ok=True)
    program = destination / "program.gcode"
    manifest = destination / "manifest.json"
    if not evaluation.allowed or evaluation.program_text is None or evaluation.manifest is None:
        for path in (program, destination / "program.nc", manifest):
            if path.exists():
                path.unlink()
        _write_export_result(destination, evaluation, program_written=False)
        return
    _write_program_files(destination, evaluation)
    _write_export_result(destination, evaluation, program_written=True)


def _write_export_result(
    destination: Path, evaluation: ExportEvaluation, *, program_written: bool,
) -> None:
    refusal = evaluation.refusal
    payload = {
        "experimental_banner": EXPERIMENTAL_BANNER,
        "physical_machining_authorized": False,
        "program_written": program_written,
        "reason_codes": [] if refusal is None else [refusal.code],
        "detail": None if refusal is None else refusal.detail,
        "plan_digest": evaluation.plan_digest,
    }
    (destination / "result.json").write_text(_stable_json(payload), encoding="utf-8")


def run_witness(package_root: Path, destination: Path, *, case: str) -> dict:
    """Verify a package and record the planner boundary. Does not emit a program."""
    if destination.resolve() == package_root.resolve():
        raise ValueError("witness destination must not be the package directory")
    destination.mkdir(parents=True, exist_ok=True)
    verification = verify_package(package_root, mode="offline")
    payload: dict = {
        "witness": "cs-pep-001",
        "case": case,
        "experimental_banner": EXPERIMENTAL_BANNER,
        "acoustic_validity": False,
        "physical_machining_authorized": False,
        "program_written": False,
        "candidate_plan": None,
        "preview": None,
        "blocked": [
            "contour_planner",
            "operational_trust",
            "operational_governed_export",
            "human_review_authority",
        ],
    }
    payload["input_manifest"] = _input_manifest(verification)
    if not verification.accepted:
        refusal = verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified")
        payload["accepted"] = False
        payload["reason_codes"] = [refusal.code]
        payload["detail"] = refusal.detail
        payload["manufacturing_check"] = {
            "declared_limits": refusal.code,
            "motion_checks": "not_run",
        }
        _write_result(destination, payload)
        payload["exit_code"] = 1
        return payload
    planner = plan_candidate(verification)
    payload["accepted"] = False
    payload["reason_codes"] = [planner.code]
    payload["detail"] = planner.detail
    payload["manufacturing_check"] = {
        "declared_limits": "passed",
        "motion_checks": "not_run",
        "reason": planner.detail,
    }
    payload["preview"] = {
        "path": "cam_creation_studio.toolpath.toolpath_to_preview",
        "status": "not_run",
        "reason": "no candidate plan",
    }
    _write_result(destination, payload)
    payload["exit_code"] = 1
    return payload


def prepare_planned_witness(
    package_root: Path, destination: Path, *, case: str,
) -> dict:
    """Verify planner inputs and write a candidate. Does not write a program."""
    _require_distinct_destination(package_root, destination)
    destination.mkdir(parents=True, exist_ok=True)
    candidate, refusal = _plan_rectangular_package(package_root)
    if refusal is not None or candidate is None:
        _unlink_planned(destination, _PLANNED_OUTPUTS)
        payload = _planned_payload(
            case=case, candidate=None, refusal=refusal or Refusal(
                codes.SCHEMA_INVALID, "rectangular plan was not produced"),
            planning_status="refused", export_status="blocked",
            program_written=False,
        )
        _write_planned_result(destination, payload)
        payload["exit_code"] = 1
        return payload
    evaluation = evaluate_generated_candidate_export(
        candidate, package_root, None, mode="offline")
    refusal = evaluation.refusal
    if refusal is None or refusal.code != codes.REVIEW_REQUIRED:
        _unlink_planned(destination, _PLANNED_OUTPUTS)
        payload = _planned_payload(
            case=case, candidate=None, refusal=refusal or Refusal(
                codes.UNSUPPORTED_CAPABILITY, "prepare did not reach review"),
            planning_status="refused", export_status="blocked",
            program_written=False,
        )
        _write_planned_result(destination, payload)
        payload["exit_code"] = 1
        return payload
    _write_candidate_files(destination, candidate)
    _unlink_planned(destination, ("program.gcode", "program.nc", "manifest.json"))
    payload = _planned_payload(
        case=case, candidate=candidate, refusal=refusal,
        planning_status="candidate_ready", export_status="blocked",
        program_written=False,
    )
    _write_planned_result(destination, payload)
    payload["exit_code"] = 1
    return payload


def export_planned_witness(
    package_root: Path,
    destination: Path,
    review_bytes: bytes,
    *,
    case: str,
) -> dict:
    """Reverify a prepared rectangle and write one experimental program."""
    _require_distinct_destination(package_root, destination)
    destination.mkdir(parents=True, exist_ok=True)
    prepared = destination / "candidate_plan.json"
    if prepared.exists():
        recorded, refusal = _recorded_input_digests(prepared)
        if refusal is not None or recorded is None:
            _unlink_planned(destination, _PLANNED_OUTPUTS)
            payload = _planned_payload(
                case=case, candidate=None, refusal=refusal or Refusal(
                    codes.SCHEMA_INVALID, "prepared candidate could not be read"),
                planning_status="refused", export_status="blocked",
                program_written=False,
            )
            _write_planned_result(destination, payload)
            payload["exit_code"] = 1
            return payload
        refusal = _prepared_inputs_still_match(package_root, recorded)
        if refusal is not None:
            _unlink_planned(destination, _PLANNED_OUTPUTS)
            payload = _planned_payload(
                case=case, candidate=None, refusal=refusal,
                planning_status="refused", export_status="blocked",
                program_written=False,
            )
            _write_planned_result(destination, payload)
            payload["exit_code"] = 1
            return payload
    candidate, refusal = _plan_rectangular_package(package_root)
    if refusal is not None or candidate is None:
        _unlink_planned(destination, _PLANNED_OUTPUTS)
        payload = _planned_payload(
            case=case, candidate=None, refusal=refusal or Refusal(
                codes.SCHEMA_INVALID, "rectangular plan was not produced"),
            planning_status="refused", export_status="blocked",
            program_written=False,
        )
        _write_planned_result(destination, payload)
        payload["exit_code"] = 1
        return payload
    evaluation = evaluate_generated_candidate_export(
        candidate, package_root, review_bytes, mode="offline")
    if not evaluation.allowed or evaluation.program_text is None or evaluation.manifest is None:
        refusal = evaluation.refusal or Refusal(
            codes.UNSUPPORTED_CAPABILITY, "experimental program was not rendered")
        if refusal.code == codes.SNAPSHOT_CHANGED:
            _unlink_planned(destination, _PLANNED_OUTPUTS)
            shown = None
        else:
            _write_candidate_files(destination, candidate)
            _unlink_planned(
                destination, ("program.gcode", "program.nc", "manifest.json"))
            shown = candidate
        payload = _planned_payload(
            case=case, candidate=shown, refusal=refusal,
            planning_status="refused" if shown is None else "candidate_ready",
            export_status="blocked", program_written=False,
        )
        _write_planned_result(destination, payload)
        payload["exit_code"] = 1
        return payload
    _write_candidate_files(destination, candidate)
    _write_program_files(destination, evaluation)
    payload = _planned_payload(
        case=case, candidate=candidate, refusal=None,
        planning_status="candidate_ready", export_status="written",
        program_written=True,
    )
    _write_planned_result(destination, payload)
    payload["exit_code"] = 0
    return payload


def parse_request_bytes_public(raw: bytes):
    """Public parser used by the gate and by structure tests."""
    return parse_request_bytes(raw)


def _load_review(
    review_bytes: bytes | None,
) -> tuple[ReviewRecord | None, Refusal | None]:
    if review_bytes is None:
        return None, None
    return parse_review_bytes(review_bytes)


def plan_digest_for(verification: VerificationResult, motions) -> str:
    """Plan digest used by the export gate. Timestamps are not inputs."""
    return _plan_digest(verification, motions)


def _plan_digest(verification: VerificationResult, motions) -> str:
    request = verification.request
    bundle = verification.bundle
    if not verification.accepted or request is None or bundle is None:
        raise TraceabilityDefect("plan digest requires a verified request and bundle")
    digests = {item.role: item.sha256 for item in bundle.snapshot.artifacts}
    return compute_plan_digest(
        request_digest_value=request_digest(request),
        artifact_digests=digests,
        strategy_fp=traceable_strategy_fingerprint(request),
        tool_diameter_mm=request.tool_diameter_mm,
        stock_allowance_mm=request.stock_allowance_mm,
        stock_id=request.stock_id,
        frame_id=request.frame_id,
        units=request.units,
        profile_id=request.profile_id,
        toolpath_digest=toolpath_digest(motions),
        motion_source=_MOTION_SOURCE_EXPLICIT,
    )


def _context(bundle: PackageBundle, trust: str) -> VerifiedImportContext:
    request = bundle.request
    limitations = (
        EXPERIMENTAL_BANNER,
        "Producer trust is an offline fixture pin, not an operational anchor.",
        "Current state is not established.",
        "Rectangular centerline planning is a separate planner-input path.",
        "Operational governed export is disabled.",
        "No human-review authority is configured.",
    )
    return VerifiedImportContext(
        request_digest=request_digest(request),
        artifact_digests=tuple(
            (item.role, item.sha256) for item in bundle.snapshot.artifacts
        ),
        compatibility_policy_digest=policy_digest(),
        maturity=assigned_maturity(bundle.admission.pin_status),
        admission_disposition=bundle.admission.disposition,
        producer_id=bundle.admission.producer_id,
        trust=trust,
        subject_id=request.subject_id,
        geometry_id=request.geometry_id,
        geometry_revision=request.geometry_revision,
        package_id=request.package_id,
        proposal_id=bundle.proposal.proposal_id,
        frame_id=request.frame_id,
        units=request.units,
        profile_id=request.profile_id,
        limitations=limitations,
    )


def _input_manifest(verification: VerificationResult) -> dict | None:
    if verification.bundle is None or verification.request is None:
        return None
    context = verification.context
    return {
        "package_id": verification.request.package_id,
        "request_sha256": verification.bundle.snapshot.request_sha256,
        "request_digest": None if context is None else context.request_digest,
        "artifacts": [
            {
                "role": item.role,
                "package_ref": item.package_ref,
                "sha256": item.sha256,
            }
            for item in verification.bundle.snapshot.artifacts
        ],
        "maturity": None if context is None else context.maturity,
        "admission_disposition": (
            None if context is None else context.admission_disposition
        ),
        "compatibility_policy_digest": policy_digest(),
        "experimental_banner": EXPERIMENTAL_BANNER,
    }


def _manifest(
    verification: VerificationResult,
    *,
    plan_digest_value: str,
    program_sha: str,
    review: ReviewRecord | None,
) -> dict:
    if verification.request is None or review is None:
        raise TraceabilityDefect("export manifest requires a request and bound review")
    return {
        "contract_version": MANIFEST_VERSION,
        "program_sha256": program_sha,
        "plan_digest": plan_digest_value,
        "plan_contract_version": PLAN_VERSION,
        "input_references": _input_manifest(verification),
        "profile_id": verification.request.profile_id,
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "planner_id": PLANNER_ID,
        "planner_version": PLANNER_VERSION,
        "motion_source": _MOTION_SOURCE_EXPLICIT,
        "review": {
            "review_id": review.review_id,
            "plan_digest": review.plan_digest,
            "policy_digest": review.policy_digest,
            "decision": review.decision,
            "experimental": review.experimental,
            "authority": review.authority,
        },
        "authority_limitations": list(AUTHORITY_LIMITATIONS),
        "experimental_banner": EXPERIMENTAL_BANNER,
    }


def _generated_manifest(
    candidate: GeneratedCandidate,
    *,
    plan_digest_value: str,
    program_sha: str,
    review: ReviewRecord,
) -> dict:
    verification = candidate.verification
    if verification.request is None:
        raise TraceabilityDefect("generated manifest requires a verified request")
    references = _input_manifest(verification) or {}
    references = dict(references)
    references["planner_input_sha256"] = candidate.additional.planner_input_sha256
    references["operation_plan_sha256"] = candidate.additional.operation_plan_sha256
    references["planner_input_ref"] = candidate.additional.planner_input_ref
    references["operation_plan_ref"] = candidate.additional.operation_plan_ref
    return {
        "contract_version": rectangle_limits.GENERATED_MANIFEST_VERSION,
        "program_sha256": program_sha,
        "plan_digest": plan_digest_value,
        "plan_contract_version": rectangle_limits.GENERATED_PLAN_VERSION,
        "input_references": references,
        "profile_id": verification.request.profile_id,
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "planner_id": rectangle_limits.PLANNER_ID,
        "planner_version": rectangle_limits.PLANNER_VERSION,
        "motion_source": rectangle_limits.MOTION_SOURCE,
        "review": {
            "review_id": review.review_id,
            "plan_digest": review.plan_digest,
            "policy_digest": review.policy_digest,
            "decision": review.decision,
            "experimental": review.experimental,
            "authority": review.authority,
        },
        "authority_limitations": list(AUTHORITY_LIMITATIONS),
        "experimental_banner": EXPERIMENTAL_BANNER,
        "human_approval": False,
        "operational_export": False,
    }


_PLANNED_OUTPUTS = (
    "candidate_plan.json",
    "preview.json",
    "program.gcode",
    "program.nc",
    "manifest.json",
)


def _plan_rectangular_package(
    package_root: Path,
) -> tuple[GeneratedCandidate | None, Refusal | None]:
    verification = verify_package(package_root, mode="offline")
    if (
        not verification.accepted
        or verification.bundle is None
        or verification.request is None
    ):
        return None, verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified")
    loaded, refusal = load_planner_inputs(
        package_root, verification.bundle.snapshot.request_raw)
    if refusal is not None or loaded is None:
        return None, refusal
    return build_generated_candidate(verification, loaded)


def _require_distinct_destination(package_root: Path, destination: Path) -> None:
    if destination.resolve() == package_root.resolve():
        raise ValueError("witness destination must not be the package directory")


def _unlink_planned(destination: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = destination / name
        if path.is_symlink() or path.exists():
            path.unlink()


def _write_program_files(destination: Path, evaluation: ExportEvaluation) -> None:
    if evaluation.program_text is None or evaluation.manifest is None:
        raise TraceabilityDefect("program files require an allowed evaluation")
    raw = evaluation.program_text.encode("utf-8")
    if (
        not evaluation.program_text.startswith(f"({EXPERIMENTAL_BANNER})\n")
        or evaluation.manifest.get("experimental_banner") != EXPERIMENTAL_BANNER
        or sha256_bytes(raw) != evaluation.program_sha256
        or evaluation.manifest.get("program_sha256") != evaluation.program_sha256
    ):
        raise TraceabilityDefect(
            "offline export lost its experimental label or digest binding")
    (destination / "program.gcode").write_bytes(raw)
    (destination / "manifest.json").write_text(
        _stable_json(evaluation.manifest), encoding="utf-8")


def _candidate_document(candidate: GeneratedCandidate) -> dict:
    plan = candidate.plan
    if not isinstance(plan, ToolpathPlan):
        raise TraceabilityDefect("generated candidate is missing a ToolpathPlan")
    toolpath_json = toolpath_to_json(plan)
    verification = candidate.verification
    request = verification.request
    bundle = verification.bundle
    if request is None or bundle is None:
        raise TraceabilityDefect("candidate document requires a verified package")
    return {
        "contract_version": rectangle_limits.GENERATED_PLAN_VERSION,
        "experimental_banner": EXPERIMENTAL_BANNER,
        "physical_machining_authorized": False,
        "human_approval": False,
        "program_exported": False,
        "planner_id": rectangle_limits.PLANNER_ID,
        "planner_version": rectangle_limits.PLANNER_VERSION,
        "motion_source": rectangle_limits.MOTION_SOURCE,
        "plan_digest": candidate.plan_digest,
        "request_sha256": bundle.snapshot.request_sha256,
        "request_digest": request_digest(request),
        "artifact_digests": {
            item.role: item.sha256 for item in bundle.snapshot.artifacts
        },
        "planner_input_sha256": candidate.additional.planner_input_sha256,
        "planner_input_ref": candidate.additional.planner_input_ref,
        "operation_plan_sha256": candidate.additional.operation_plan_sha256,
        "operation_plan_ref": candidate.additional.operation_plan_ref,
        "definition_id": candidate.definition_id,
        "binding_id": candidate.binding_id,
        "geometry_ids": list(candidate.geometry_ids),
        "recommendation_id": candidate.recommendation_id,
        "planned_cut_feed_mm_min": candidate.planned_cut_feed_mm_min,
        "planned_plunge_feed_mm_min": candidate.planned_plunge_feed_mm_min,
        "tool_id": candidate.tool_id,
        "tool_diameter_mm": candidate.tool_diameter_mm,
        "tool_flutes": candidate.tool_flutes,
        "material_id": candidate.material_id,
        "strategy_fingerprint": plan.strategy_fingerprint,
        "frame_id": request.frame_id,
        "units": request.units,
        "profile_id": request.profile_id,
        "stock_allowance_mm": request.stock_allowance_mm,
        "policy_digest": policy_digest(),
        "postprocessor_id": POSTPROCESSOR_ID,
        "postprocessor_version": postprocessor_version(),
        "toolpath_digest": toolpath_digest(plan_motions(plan)),
        "toolpath_sha256": sha256_bytes(toolpath_json.encode("utf-8")),
        "local_limits": {
            "max_depth_levels": rectangle_limits.MAX_DEPTH_LEVELS,
            "max_motions": rectangle_limits.MAX_MOTIONS,
            "max_planner_input_bytes": rectangle_limits.MAX_PLANNER_INPUT_BYTES,
        },
        "toolpath": toolpath_to_dict(plan),
    }


def _preview_document(candidate: GeneratedCandidate) -> dict:
    plan = candidate.plan
    if not isinstance(plan, ToolpathPlan):
        raise TraceabilityDefect("preview requires a ToolpathPlan")
    segments = []
    for segment in toolpath_to_preview(plan):
        segments.append({
            "distance": segment.distance,
            "end": [segment.end.x, segment.end.y, segment.end.z],
            "feed": segment.feed,
            "start": [segment.start.x, segment.start.y, segment.start.z],
            "type": segment.type,
        })
    return {
        "authoritative": False,
        "experimental_banner": EXPERIMENTAL_BANNER,
        "plan_digest": candidate.plan_digest,
        "projection": "cam_creation_studio.toolpath.toolpath_to_preview",
        "segments": segments,
    }


def _write_candidate_files(destination: Path, candidate: GeneratedCandidate) -> None:
    (destination / "candidate_plan.json").write_text(
        _stable_json(_candidate_document(candidate)), encoding="utf-8")
    (destination / "preview.json").write_text(
        _stable_json(_preview_document(candidate)), encoding="utf-8")


def _planned_payload(
    *,
    case: str,
    candidate: GeneratedCandidate | None,
    refusal: Refusal | None,
    planning_status: str,
    export_status: str,
    program_written: bool,
) -> dict:
    return {
        "case": case,
        "detail": None if refusal is None else refusal.detail,
        "experimental_banner": EXPERIMENTAL_BANNER,
        "export_status": export_status,
        "human_approval": False,
        "physical_machining_authorized": False,
        "plan_digest": None if candidate is None else candidate.plan_digest,
        "planning_status": planning_status,
        "program_exported": False,
        "program_written": program_written,
        "reason_codes": [] if refusal is None else [refusal.code],
        "witness": "cs-017",
    }


def _write_planned_result(destination: Path, payload: dict) -> None:
    public = {key: value for key, value in payload.items() if key != "exit_code"}
    (destination / "result.json").write_text(_stable_json(public), encoding="utf-8")


def _recorded_input_digests(
    path: Path,
) -> tuple[dict | None, Refusal | None]:
    try:
        document = load_bounded_json(path.read_bytes())
    except _ParseFailure as exc:
        return None, Refusal(exc.code, exc.detail)
    except OSError as exc:
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, f"prepared candidate is unreadable: {exc}")
    required = (
        "planner_input_sha256", "operation_plan_sha256",
        "planner_input_ref", "operation_plan_ref", "plan_digest",
    )
    if any(key not in document for key in required):
        return None, Refusal(
            codes.SCHEMA_INVALID, "prepared candidate is missing input digests")
    return {key: document[key] for key in required}, None


def _prepared_inputs_still_match(
    package_root: Path, recorded: dict,
) -> Refusal | None:
    pairs = (
        (recorded["planner_input_ref"], recorded["planner_input_sha256"],
         "planner input"),
        (recorded["operation_plan_ref"], recorded["operation_plan_sha256"],
         "operation plan"),
    )
    for package_ref, digest, label in pairs:
        if not isinstance(package_ref, str) or not isinstance(digest, str):
            return Refusal(
                codes.SCHEMA_INVALID, "prepared candidate digests are not strings")
        path, refusal = resolve_package_ref(package_root, package_ref)
        if refusal is not None or path is None:
            return refusal
        raw, refusal = read_bounded(path, rectangle_limits.MAX_PLANNER_INPUT_BYTES)
        if refusal is not None or raw is None:
            return refusal
        if sha256_bytes(raw) != digest:
            return Refusal(
                codes.SNAPSHOT_CHANGED,
                f"{label} bytes changed after prepare",
            )
    return None


def _rejected(refusal: Refusal) -> VerificationResult:
    return VerificationResult(False, refusal, None, None, None)


def _refused(
    refusal: Refusal,
    verification: VerificationResult | None = None,
    plan_digest_value: str | None = None,
) -> ExportEvaluation:
    return ExportEvaluation(
        allowed=False,
        refusal=refusal,
        program_text=None,
        program_sha256=None,
        manifest=None,
        plan_digest=plan_digest_value,
        input_manifest=None if verification is None else _input_manifest(verification),
    )


def _origins(document: dict) -> list:
    found = []
    if "workflow_origin" in document:
        found.append(document["workflow_origin"])
    for key in ("config", "job"):
        child = document.get(key)
        if isinstance(child, dict) and "workflow_origin" in child:
            found.append(child["workflow_origin"])
    return found


def _has_marker(document: dict) -> bool:
    # These namespaces and artifact references are reserved, even malformed.
    if any(key in document for key in _MARKERS):
        return True
    if _admission_marker(document) or _request_marker(document):
        return True
    for key in ("config", "job"):
        child = document.get(key)
        if isinstance(child, dict) and (
            any(name in child for name in _MARKERS)
            or _admission_marker(child)
            or _request_marker(child)
        ):
            return True
    return False


def _admission_marker(document: dict) -> bool:
    admission = document.get("admission")
    if not isinstance(admission, dict):
        return False
    # A generic note called "admission" is not provenance. An artifact-shaped
    # object remains governed even when incomplete or unknown-versioned.
    return any(key in admission for key in _ADMISSION_KEYS)


def _request_marker(document: dict) -> bool:
    version = document.get("contract_version")
    return isinstance(version, str) and version.startswith(
        "creation-studio.traceable-planning-request/")


def _stable_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_result(destination: Path, payload: dict) -> None:
    public = {key: value for key, value in payload.items() if key != "exit_code"}
    (destination / "result.json").write_text(_stable_json(public), encoding="utf-8")
    for name in (
        "program.gcode", "program.nc", "manifest.json",
        "candidate_plan.json", "preview.json",
    ):
        stray = destination / name
        if stray.exists():
            stray.unlink()
