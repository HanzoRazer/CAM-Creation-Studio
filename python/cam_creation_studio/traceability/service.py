"""Shared traceable-planning gate.

Parsing, resolution, identity, trust, manufacturing checks, review binding,
and governed export decisions all live here. The witness CLI and
``camstudio generate`` call this module. They do not keep a second copy of
the rules.
"""

from __future__ import annotations

from pathlib import Path

from ..toolpath.models import MotionSegment
from . import codes
from .artifacts import load_package, resolve_package_ref, reverify_snapshot, read_exact
from .bounds import check_declared_request, check_motions
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
from .identity import check_identity
from .models import (
    ExportEvaluation,
    PackageBundle,
    PlanningRequest,
    Refusal,
    ReviewRecord,
    VerificationResult,
    VerifiedImportContext,
)
from .parsing import parse_request_bytes, parse_review_bytes
from .planning import (
    compute_plan_digest,
    plan_candidate,
    request_digest,
    traceable_strategy_fingerprint,
)
from .posting import render_experimental_program, toolpath_digest
from .review import bind_review
from .trust import assess_producer

_MARKERS = (
    "upstream_artifacts",
    "admission",
    "traceable_planning",
    "traceable_plan",
)
_MOTION_SOURCE_EXPLICIT = "explicit_linear_motion"


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
    and do not produce a program.
    """
    if not verification.accepted or verification.request is None or verification.bundle is None or verification.context is None:
        return _refused(verification.refusal or Refusal(
            codes.SCHEMA_INVALID, "package was not verified"), verification)
    refusal = reverify_snapshot(verification.bundle.snapshot, package_root)
    if refusal is not None:
        return _refused(refusal, verification)
    refusal = check_motions(verification.request, motions)
    if refusal is not None:
        return _refused(refusal, verification)
    plan_fp = _plan_digest(verification, motions)
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
    program, refusal = render_experimental_program(
        motions, clearance_mm=verification.request.clearance_mm)
    if refusal is not None or program is None:
        return _refused(refusal or Refusal(
            codes.UNSUPPORTED_CAPABILITY, "program was not rendered"),
            verification, plan_fp)
    manifest = _manifest(
        verification,
        plan_digest_value=plan_fp,
        program_sha=sha256_bytes(program.encode("utf-8")),
        review=review,
    )
    return ExportEvaluation(
        allowed=True,
        refusal=None,
        program_text=program,
        program_sha256=sha256_bytes(program.encode("utf-8")),
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
        return
    program.write_text(evaluation.program_text, encoding="utf-8")
    manifest.write_text(_stable_json(evaluation.manifest), encoding="utf-8")


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
    assert request is not None and bundle is not None
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
        "Contour planner is unavailable.",
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
    assert verification.request is not None and review is not None
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
    if any(key in document for key in _MARKERS):
        return True
    for key in ("config", "job"):
        child = document.get(key)
        if isinstance(child, dict) and any(name in child for name in _MARKERS):
            return True
    return False


def _stable_json(payload: dict) -> str:
    import json
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_result(destination: Path, payload: dict) -> None:
    public = {key: value for key, value in payload.items() if key != "exit_code"}
    (destination / "result.json").write_text(_stable_json(public), encoding="utf-8")
    for name in ("program.gcode", "program.nc", "manifest.json"):
        stray = destination / name
        if stray.exists():
            stray.unlink()
