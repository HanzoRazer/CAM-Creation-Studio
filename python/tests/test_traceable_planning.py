"""Traceable planning boundary (CS-PEP-001)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from cam_creation_studio.cli.main import main
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.builders import make_arc_motion, make_linear_motion
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.traceability.codes import REASON_CODES
from cam_creation_studio.traceability.compatibility import (
    REQUEST_FIELDS,
    REQUEST_VERSION,
    REVIEW_VERSION,
    policy_digest,
)
from cam_creation_studio.traceability.encoding import digest_json, sha256_bytes
from cam_creation_studio.traceability.planning import compute_plan_digest
from cam_creation_studio.traceability.service import (
    classify_generate_document,
    evaluate_explicit_motion_export,
    evaluate_verified_motion_export,
    export_governed_package,
    plan_digest_for,
    run_witness,
    verify_package,
    write_offline_export,
)
from cam_creation_studio.traceability.synthetic import (
    CENTER,
    DEPTH_LEVELS,
    REMOVAL,
    TOOL_DIAMETER_MM,
    TOLERANCE_MM,
    build_synthetic_package,
)
from cam_creation_studio.traceability.parsing import parse_request_bytes

_REPO = Path(__file__).resolve().parents[2]


def _package(tmp_path: Path, variant: str = "consistent") -> Path:
    return build_synthetic_package(tmp_path / variant, variant)


def _request_bytes(package: Path) -> bytes:
    return (package / "request.json").read_bytes()


def _mutate_request(package: Path, fn) -> None:
    document = json.loads(_request_bytes(package))
    fn(document)
    (package / "request.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contour(x0, y0, x1, y1, depths, clearance=5.0):
    motions = []
    index = 0
    for depth in depths:
        z = -float(depth)
        approach = Point(x0, y0, clearance + 1.0 if not motions else clearance)
        start = Point(x0, y0, clearance)
        landed = Point(x0, y0, z)
        motions.append(make_linear_motion(
            MotionKind.TRAVEL, approach, start, index=index))
        index += 1
        motions.append(make_linear_motion(
            MotionKind.PLUNGE, start, landed, index=index, planned_feed_mm_min=300.0))
        index += 1
        previous = landed
        for corner in (
            Point(x1, y0, z), Point(x1, y1, z), Point(x0, y1, z), Point(x0, y0, z),
        ):
            motions.append(make_linear_motion(
                MotionKind.CUT, previous, corner, index=index,
                planned_feed_mm_min=800.0))
            index += 1
            previous = corner
        motions.append(make_linear_motion(
            MotionKind.RETRACT, previous, Point(x0, y0, clearance), index=index))
        index += 1
    return tuple(motions)


def _good_motions():
    x0, y0, x1, y1 = CENTER
    return _contour(x0, y0, x1, y1, DEPTH_LEVELS)


def _review(plan_digest: str, **overrides) -> bytes:
    document = {
        "authority": "fixture_binding_only",
        "contract_version": REVIEW_VERSION,
        "decision": "accepted",
        "experimental": True,
        "plan_digest": plan_digest,
        "policy_digest": policy_digest(),
        "recorded_at": "2026-10-25T18:00:00Z",
        "review_id": "revw-fixture-1",
        "reviewer_ref": "synthetic-fixture-reviewer",
    }
    document.update(overrides)
    return (json.dumps(document, sort_keys=True) + "\n").encode("utf-8")


def _oracle_disk_inside(x, y, radius, rect):
    """Independent rectangle test. Not the production checker."""
    x_min, y_min, x_max, y_max = rect
    return (
        x - radius >= x_min
        and x + radius <= x_max
        and y - radius >= y_min
        and y + radius <= y_max
    )


def _oracle_segment_inside(start, end, radius, rect):
    return (
        _oracle_disk_inside(start[0], start[1], radius, rect)
        and _oracle_disk_inside(end[0], end[1], radius, rect)
    )


def test_reason_vocabulary_is_closed_and_documented():
    text = (_REPO / "docs" / "architecture" / "traceable-planning.md").read_text(
        encoding="utf-8")
    for code in REASON_CODES:
        assert code in text
    assert len(REASON_CODES) == len(set(REASON_CODES))


def test_request_schema_required_fields_match_the_parser():
    schema = json.loads(
        (_REPO / "schemas" / "traceable_planning_request_v1.schema.json").read_text(
            encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert tuple(schema["required"]) == REQUEST_FIELDS


def test_consistent_package_verifies_as_experimental_fixture(tmp_path):
    package = _package(tmp_path)
    result = verify_package(package, mode="offline")
    assert result.accepted
    assert result.refusal is None
    assert result.context is not None
    assert result.context.maturity == "experimental"
    assert result.context.trust == "offline_fixture"
    assert result.context.admission_disposition == "admitted_for_human_review"
    assert result.context.geometry_revision == "rev-1"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"", "SCHEMA_INVALID"),
        (b"[]", "SCHEMA_INVALID"),
        (b"{", "SCHEMA_INVALID"),
        (b'{"a": 1, "a": 2}', "SCHEMA_INVALID"),
        (b'{"contract_version": "nope"}', "SCHEMA_INVALID"),
        ('{"depth": NaN}'.encode(), "SCHEMA_INVALID"),
        ('{"depth": Infinity}'.encode(), "SCHEMA_INVALID"),
        (b"\xef\xbb\xbf{}", "SCHEMA_INVALID"),
        (b"\xff", "SCHEMA_INVALID"),
    ],
)
def test_malformed_request_bytes_are_refusals(raw, code):
    _request, refusal = parse_request_bytes(raw)
    assert refusal is not None
    assert refusal.code == code


def test_structural_request_variants_refuse_without_raising(tmp_path):
    package = _package(tmp_path)
    document = json.loads(_request_bytes(package))

    def parse(mutator):
        body = json.loads(json.dumps(document))
        mutator(body)
        return parse_request_bytes(json.dumps(body).encode("utf-8"))

    _request, refusal = parse(lambda body: body.pop("request_id"))
    assert refusal.code == "SCHEMA_INVALID"
    _request, refusal = parse(lambda body: body.__setitem__("request_id", 12))
    assert refusal.code == "SCHEMA_INVALID"
    _request, refusal = parse(lambda body: body.__setitem__("request_id", None))
    assert refusal.code == "SCHEMA_INVALID"
    _request, refusal = parse(
        lambda body: body.__setitem__("contract_version", ["v1"]))
    assert refusal.code == "UNSUPPORTED_VERSION"
    _request, refusal = parse(
        lambda body: body.__setitem__("contract_version", {"version": 1}))
    assert refusal.code == "UNSUPPORTED_VERSION"
    _request, refusal = parse(
        lambda body: body.__setitem__("contract_version", REQUEST_VERSION + ".next"))
    assert refusal.code == "UNSUPPORTED_VERSION"
    _request, refusal = parse(lambda body: body.__setitem__("label", "manual"))
    assert refusal.code == "SCHEMA_INVALID"
    _request, refusal = parse(
        lambda body: body.__setitem__("workflow_origin", "human_authored"))
    assert refusal.code == "PROVENANCE_IMMUTABLE"
    _request, refusal = parse(
        lambda body: body["operation"].__setitem__("type", "pocket"))
    assert refusal.code == "UNSUPPORTED_CAPABILITY"
    _request, refusal = parse(
        lambda body: body["strategy"].__setitem__("depth_levels_mm", [1.0, math.nan]))
    assert refusal.code == "SCHEMA_INVALID"


def test_missing_symlink_and_escape_references(tmp_path):
    package = _package(tmp_path / "pkg")
    outside = tmp_path / "secret.json"
    outside.write_text("{}\n", encoding="utf-8")
    link = package / "linked.json"
    link.symlink_to(outside)
    _mutate_request(package, lambda body: body["upstream_artifacts"][0].update({
        "package_ref": "linked.json",
        "sha256": sha256_bytes(link.read_bytes()),
    }))
    result = verify_package(package)
    assert result.refusal is not None
    assert result.refusal.code == "REFERENCE_UNRESOLVED"

    package = _package(tmp_path / "escape")
    _mutate_request(package, lambda body: body["upstream_artifacts"][0].update({
        "package_ref": "../secret.json",
    }))
    result = verify_package(package)
    assert result.refusal.code == "REFERENCE_UNRESOLVED"

    package = _package(tmp_path / "missing")
    _mutate_request(package, lambda body: body["upstream_artifacts"][0].update({
        "package_ref": "missing.json",
    }))
    result = verify_package(package)
    assert result.refusal.code == "REFERENCE_UNRESOLVED"

    package = _package(tmp_path / "remote")
    _mutate_request(package, lambda body: body["upstream_artifacts"][0].update({
        "package_ref": "https://example.invalid/proposal.json",
    }))
    result = verify_package(package)
    assert result.refusal.code == "REFERENCE_UNRESOLVED"


def test_changed_bytes_and_reserialization_do_not_match(tmp_path):
    package = _package(tmp_path / "tamper")
    proposal = package / "proposal.json"
    original = proposal.read_bytes()
    proposal.write_bytes(original.replace(b"prop-coupon-1", b"prop-coupon-2"))
    result = verify_package(package)
    assert result.refusal is not None
    assert result.refusal.code == "DIGEST_MISMATCH"

    package = _package(tmp_path / "reformat")
    proposal = package / "proposal.json"
    parsed = json.loads(proposal.read_text(encoding="utf-8"))
    proposal.write_text(json.dumps(parsed, indent=4) + "\n", encoding="utf-8")
    result = verify_package(package)
    assert result.refusal.code == "DIGEST_MISMATCH"


def test_snapshot_change_between_verify_and_export_writes_nothing(tmp_path):
    package = _package(tmp_path / "pkg")
    verification = verify_package(package)
    assert verification.accepted
    proposal = package / "proposal.json"
    proposal.write_bytes(proposal.read_bytes() + b" \n")
    motions = _good_motions()
    digest = plan_digest_for(verification, motions)
    evaluation = evaluate_verified_motion_export(
        verification, package, motions, _review(digest), mode="offline")
    assert evaluation.allowed is False
    assert evaluation.refusal.code == "SNAPSHOT_CHANGED"
    assert evaluation.program_text is None
    destination = tmp_path / "out"
    write_offline_export(destination, evaluation)
    assert not (destination / "program.gcode").exists()


@pytest.mark.parametrize(
    ("variant", "code"),
    [
        ("geometry", "GEOMETRY_REVISION_MISMATCH"),
        ("admission", "PROPOSAL_BINDING_MISMATCH"),
        ("subject", "SUBJECT_MISMATCH"),
        ("package", "PACKAGE_MISMATCH"),
        ("units", "UNITS_MISMATCH"),
        ("frame", "FRAME_MISMATCH"),
        ("relabel", "PROVENANCE_IMMUTABLE"),
    ],
)
def test_identity_variants(tmp_path, variant, code):
    result = verify_package(_package(tmp_path, variant))
    assert result.accepted is False
    assert result.refusal.code == code


def test_forged_producer_and_favorable_literals(tmp_path):
    forged = verify_package(_package(tmp_path / "forged", "forged_producer"))
    assert forged.refusal.code == "UNTRUSTED_ADMISSION"
    favorable_package = _package(tmp_path / "fav", "favorable")
    favorable = verify_package(favorable_package)
    assert favorable.accepted
    assert favorable.context.maturity == "experimental"
    assert favorable.context.admission_disposition == "admitted_for_human_review"
    operational = export_governed_package(favorable_package)
    assert operational.allowed is False
    assert operational.program_text is None
    assert operational.refusal.code == "EXPERIMENTAL_ONLY"


def test_current_state_claim_is_not_accepted(tmp_path):
    package = _package(tmp_path)
    admission_path = package / "admission.json"
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    admission["current_state"] = "current"
    raw = (json.dumps(admission, indent=2, sort_keys=True) + "\n").encode("utf-8")
    admission_path.write_bytes(raw)
    digest = sha256_bytes(raw)
    _mutate_request(package, lambda body: _set_role_sha(body, "admission", digest))
    result = verify_package(package)
    assert result.refusal.code == "CURRENT_STATE_UNAVAILABLE"


def _set_role_sha(body, role, digest):
    for ref in body["upstream_artifacts"]:
        if ref["role"] == role:
            ref["sha256"] = digest


def test_unknown_profile_is_refused(tmp_path):
    package = _package(tmp_path)
    _mutate_request(package, lambda body: body["upstream_artifacts"][0].update({
        "contract_version": "fixture-2",
    }))
    result = verify_package(package)
    assert result.refusal.code == "UNSUPPORTED_VERSION"


def test_declared_depth_beyond_limit_refuses_without_a_program(tmp_path):
    package = _package(tmp_path, "depth")
    result = verify_package(package)
    assert result.refusal.code == "DEPTH_LIMIT_EXCEEDED"
    destination = tmp_path / "witness-depth"
    payload = run_witness(package, destination, case="depth")
    assert payload["program_written"] is False
    assert payload["reason_codes"] == ["DEPTH_LIMIT_EXCEEDED"]
    assert list(destination.iterdir()) == [destination / "result.json"]


def test_rectangular_witness_matches_independent_oracle(tmp_path):
    package = _package(tmp_path)
    verification = verify_package(package)
    assert verification.accepted
    radius = TOOL_DIAMETER_MM / 2.0 + TOLERANCE_MM
    motions = _good_motions()
    for motion in motions:
        if motion.kind.value not in ("cut", "plunge"):
            continue
        assert _oracle_segment_inside(
            (motion.start.x, motion.start.y),
            (motion.end.x, motion.end.y),
            radius,
            REMOVAL,
        )
    digest = plan_digest_for(verification, motions)
    evaluation = evaluate_explicit_motion_export(
        package, motions, _review(digest), mode="offline")
    assert evaluation.allowed
    assert evaluation.program_text.startswith("(EXPERIMENTAL — NOT FOR MACHINING)")
    assert "G21" in evaluation.program_text
    assert "G1" in evaluation.program_text
    assert evaluation.manifest["motion_source"] == "explicit_linear_motion"
    assert evaluation.manifest["planner_id"] == "unavailable"
    assert "acoustic" in " ".join(evaluation.manifest["authority_limitations"]).lower() or any(
        "acoustic" in item.lower() for item in evaluation.manifest["authority_limitations"]
    )


def test_centerline_inside_envelope_outside_is_refused(tmp_path):
    package = _package(tmp_path)
    radius = TOOL_DIAMETER_MM / 2.0 + TOLERANCE_MM
    # x=12 and x=68 sit inside the removal span [10, 70], but the cutter
    # disk of radius 3.05 does not.
    start = (12.0, 25.0)
    end = (68.0, 25.0)
    assert 10.0 < start[0] < 70.0 and 10.0 < end[0] < 70.0
    assert _oracle_segment_inside(start, end, 0.0, REMOVAL)
    assert not _oracle_segment_inside(start, end, radius, REMOVAL)
    motions = (
        make_linear_motion(
            MotionKind.TRAVEL, Point(12, 25, 6), Point(12, 25, 5), index=0),
        make_linear_motion(
            MotionKind.PLUNGE, Point(12, 25, 5), Point(12, 25, -1),
            index=1, planned_feed_mm_min=300.0),
        make_linear_motion(
            MotionKind.CUT, Point(12, 25, -1), Point(68, 25, -1),
            index=2, planned_feed_mm_min=800.0),
        make_linear_motion(
            MotionKind.RETRACT, Point(68, 25, -1), Point(68, 25, 5), index=3),
    )
    evaluation = evaluate_explicit_motion_export(
        package, motions, None, mode="offline")
    assert evaluation.allowed is False
    assert evaluation.refusal.code == "REMOVAL_BOUND_EXCEEDED"
    assert evaluation.program_text is None


def test_excessive_depth_clearance_arc_and_profile(tmp_path):
    package = _package(tmp_path)
    deep = _contour(*CENTER, (4.0,))
    evaluation = evaluate_explicit_motion_export(package, deep, None, mode="offline")
    assert evaluation.refusal.code == "DEPTH_LIMIT_EXCEEDED"

    low_travel = (
        make_linear_motion(
            MotionKind.TRAVEL, Point(20, 15, 5), Point(20, 15, 1), index=0),
    )
    evaluation = evaluate_explicit_motion_export(
        package, low_travel, None, mode="offline")
    assert evaluation.refusal.code == "CLEARANCE_VIOLATION"

    arc = (
        make_arc_motion(
            Point(30, 15, -1), Point(20, 25, -1), Point(20, 15, -1),
            clockwise=False, index=0, planned_feed_mm_min=800.0),
    )
    evaluation = evaluate_explicit_motion_export(package, arc, None, mode="offline")
    assert evaluation.refusal.code == "UNSUPPORTED_CAPABILITY"

    _mutate_request(package, lambda body: body["machine_profile"].__setitem__(
        "id", "genericLaser"))
    result = verify_package(package)
    assert result.refusal.code == "PROFILE_UNSUPPORTED"


def test_missing_tolerance_is_not_treated_as_zero(tmp_path):
    package = _package(tmp_path)
    verification = verify_package(package)
    request = verification.request
    object.__setattr__(request, "positional_tolerance_mm", None)
    from cam_creation_studio.traceability.bounds import check_motions
    refusal = check_motions(request, _good_motions())
    assert refusal.code == "UNSUPPORTED_CAPABILITY"


def test_admission_alone_cannot_approve_and_copied_review_fails(tmp_path):
    package = _package(tmp_path)
    motions = _good_motions()
    missing = evaluate_explicit_motion_export(package, motions, None, mode="offline")
    assert missing.refusal.code == "REVIEW_REQUIRED"
    assert missing.program_text is None
    verification = verify_package(package)
    digest = plan_digest_for(verification, motions)
    copied = evaluate_explicit_motion_export(
        package, motions, _review("0" * 64), mode="offline")
    assert copied.refusal.code == "PLAN_CHANGED"
    accepted = evaluate_explicit_motion_export(
        package, motions, _review(digest), mode="operational")
    assert accepted.refusal.code == "EXPERIMENTAL_ONLY"
    assert accepted.program_text is None


def test_input_changes_invalidate_plan_digest_and_review(tmp_path):
    package = _package(tmp_path)
    verification = verify_package(package)
    motions = _good_motions()
    base = plan_digest_for(verification, motions)
    request = verification.request
    changed = []
    variants = {
        "tool_diameter_mm": 8.0,
        "stock_allowance_mm": 0.2,
        "depth_levels_mm": (1.0, 2.5),
        "clearance_mm": 6.0,
        "profile_id": "synthetic-router-mm-alt",
        "frame_id": "other-frame",
        "stock_id": "stock-other",
    }
    for name, value in variants.items():
        object.__setattr__(request, name, value)
        changed.append(plan_digest_for(verification, motions))
        object.__setattr__(request, name, getattr(build_request_snapshot(package), name))
    assert all(item != base for item in changed)
    other_motion = _contour(*CENTER, (1.0,))
    assert plan_digest_for(verification, other_motion) != base
    stale = evaluate_explicit_motion_export(
        package, motions, _review(base), mode="offline")
    assert stale.allowed
    moved = evaluate_explicit_motion_export(
        package, other_motion, _review(base), mode="offline")
    assert moved.refusal.code == "PLAN_CHANGED"


def build_request_snapshot(package: Path):
    return verify_package(package).request


def test_policy_digest_change_invalidates_review(tmp_path, monkeypatch):
    package = _package(tmp_path)
    motions = _good_motions()
    verification = verify_package(package)
    digest = plan_digest_for(verification, motions)
    review = _review(digest)
    ok = evaluate_explicit_motion_export(package, motions, review, mode="offline")
    assert ok.allowed
    import cam_creation_studio.traceability.compatibility as compatibility
    monkeypatch.setattr(compatibility, "PLANNER_VERSION", "unavailable-next")
    refused = evaluate_explicit_motion_export(package, motions, review, mode="offline")
    assert refused.allowed is False
    assert refused.refusal.code == "POLICY_UNSUPPORTED"


def test_repeatable_digests_ignore_review_timestamp(tmp_path):
    package = _package(tmp_path)
    motions = _good_motions()
    first = verify_package(package)
    second = verify_package(package)
    assert first.context.request_digest == second.context.request_digest
    digest = plan_digest_for(first, motions)
    assert plan_digest_for(second, motions) == digest
    early = evaluate_explicit_motion_export(
        package, motions, _review(digest, recorded_at="2026-10-25T18:00:00Z"),
        mode="offline")
    late = evaluate_explicit_motion_export(
        package, motions, _review(digest, recorded_at="2026-10-25T19:30:00+00:00"),
        mode="offline")
    assert early.program_sha256 == late.program_sha256
    assert early.plan_digest == late.plan_digest
    assert "2026-10-25T18:00:00Z" not in early.program_text
    again = compute_plan_digest(
        request_digest_value=first.context.request_digest,
        artifact_digests=dict(first.context.artifact_digests),
        strategy_fp=early.manifest["plan_digest"] and plan_digest_for(first, motions),
        tool_diameter_mm=first.request.tool_diameter_mm,
        stock_allowance_mm=first.request.stock_allowance_mm,
        stock_id=first.request.stock_id,
        frame_id=first.request.frame_id,
        units=first.request.units,
        profile_id=first.request.profile_id,
        toolpath_digest=digest_json({"ignored": False}),
        motion_source="explicit_linear_motion",
    )
    assert again != digest


def test_ordinary_generate_still_runs_and_governed_cannot_be_relabeled(tmp_path, capsys):
    job = {
        "config": {"machine": "genericCnc", "units": "mm", "safeZ": 5},
        "job": {"mode": "manual", "label": "square", "moves": [
            {"type": "G0", "x": 0, "y": 0, "z": 5},
            {"type": "G1", "x": 10, "y": 0, "f": 800},
        ]},
    }
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    assert classify_generate_document(job) == "ordinary"
    assert main(["generate", str(path)]) == 0
    assert "G21" in capsys.readouterr().out

    governed = json.loads(json.dumps(job))
    governed["workflow_origin"] = "imported"
    governed["job"]["label"] = "unrestricted manual job"
    governed_path = tmp_path / "governed.json"
    governed_path.write_text(json.dumps(governed), encoding="utf-8")
    output = tmp_path / "out.gcode"
    assert classify_generate_document(governed) == "governed"
    code = main(["generate", str(governed_path), "-o", str(output), "--json"])
    captured = capsys.readouterr()
    assert code == 1
    assert not output.exists()
    payload = json.loads(captured.out)
    assert "gcode" not in payload
    assert payload["reason_code"] == "EXPERIMENTAL_ONLY"
    assert payload["program_written"] is False

    stripped = json.loads(json.dumps(job))
    stripped["workflow_origin"] = "human_authored"
    stripped["upstream_artifacts"] = [{"role": "admission"}]
    stripped["job"]["label"] = "manual"
    assert classify_generate_document(stripped) == "provenance_stripped"
    stripped_path = tmp_path / "stripped.json"
    stripped_path.write_text(json.dumps(stripped), encoding="utf-8")
    code = main(["generate", str(stripped_path), "-o", str(output)])
    assert code == 1
    assert not output.exists()
    assert "PROVENANCE_IMMUTABLE" in capsys.readouterr().err


def test_witness_cases_use_distinct_directories_and_no_program(tmp_path):
    cases = {
        "consistent": "UNSUPPORTED_CAPABILITY",
        "depth": "DEPTH_LIMIT_EXCEEDED",
        "geometry": "GEOMETRY_REVISION_MISMATCH",
        "admission": "PROPOSAL_BINDING_MISMATCH",
    }
    for name, code in cases.items():
        package = _package(tmp_path / f"pkg-{name}", name)
        destination = tmp_path / f"out-{name}"
        payload = run_witness(package, destination, case=name)
        assert payload["reason_codes"] == [code]
        assert payload["program_written"] is False
        names = sorted(path.name for path in destination.iterdir())
        assert names == ["result.json"]
        saved = json.loads((destination / "result.json").read_text(encoding="utf-8"))
        assert saved["experimental_banner"] == "EXPERIMENTAL — NOT FOR MACHINING"
        assert saved["physical_machining_authorized"] is False
        assert saved["candidate_plan"] is None


def test_witness_cli_refusal_is_nonzero(tmp_path):
    package = _package(tmp_path / "pkg", "geometry")
    destination = tmp_path / "cli-out"
    script = _REPO / "tools" / "run_traceable_planning_witness.py"
    import subprocess
    import sys
    completed = subprocess.run(
        [sys.executable, str(script), "--package", str(package),
         "--destination", str(destination), "--case", "geometry"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    body = json.loads(completed.stdout)
    assert body["reason_codes"] == ["GEOMETRY_REVISION_MISMATCH"]
    assert body["program_written"] is False
    assert not (destination / "program.gcode").exists()


def test_committed_fixtures_match_declared_byte_digests():
    root = Path(__file__).resolve().parent / "fixtures" / "traceable_planning"
    expected = {
        "coupon_consistent": None,
        "coupon_depth": "DEPTH_LIMIT_EXCEEDED",
        "coupon_geometry": "GEOMETRY_REVISION_MISMATCH",
        "coupon_admission": "PROPOSAL_BINDING_MISMATCH",
    }
    for name, code in expected.items():
        package = root / name
        request = json.loads((package / "request.json").read_text(encoding="utf-8"))
        for ref in request["upstream_artifacts"]:
            raw = (package / ref["package_ref"]).read_bytes()
            assert sha256_bytes(raw) == ref["sha256"]
        result = verify_package(package)
        if code is None:
            assert result.accepted
        else:
            assert result.refusal.code == code


def test_key_order_does_not_change_request_digest(tmp_path):
    package = _package(tmp_path)
    first = verify_package(package).context.request_digest
    document = json.loads(_request_bytes(package))
    reversed_doc = {key: document[key] for key in reversed(list(document))}
    (package / "request.json").write_text(
        json.dumps(reversed_doc, indent=2) + "\n", encoding="utf-8")
    second = verify_package(package).context.request_digest
    assert first == second
