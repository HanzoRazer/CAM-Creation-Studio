"""Prepare, fixture review, and offline export for one rectangle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cam_creation_studio.planning.limits import MAX_PLANNER_INPUT_BYTES
from cam_creation_studio.traceability.service import (
    evaluate_explicit_motion_export,
    evaluate_generated_candidate_export,
    export_planned_witness,
    export_planned_witness_from_file,
    prepare_planned_witness,
    run_witness,
    verify_package,
)
from cam_creation_studio.traceability.synthetic import build_synthetic_package
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.builders import make_linear_motion
from cam_creation_studio.shared.geometry import Point
from support.closed_schema import load_schema, validate
from support.fixture_review import fixture_review_bytes
from support.rectangle_planned import (
    CENTER,
    CUT_FEED,
    make_operation_plan,
    write_planned_package,
)
from cam_creation_studio.operations.serialization import operation_plan_to_json
from cam_creation_studio.traceability.encoding import sha256_bytes

_REPO = Path(__file__).resolve().parents[2]
_SCHEMAS = _REPO / "schemas"
_SCRIPT = _REPO / "tools" / "run_traceable_planning_witness.py"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "traceable_planning" / "rectangle_planned"


def _package(tmp_path: Path) -> Path:
    return write_planned_package(tmp_path / "rectangle_planned")


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        check=False, capture_output=True, text=True,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_prepare_requires_review_and_keeps_candidate(tmp_path):
    package = _package(tmp_path)
    destination = tmp_path / "prepare"
    payload = prepare_planned_witness(package, destination, case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["planning_status"] == "candidate_ready"
    assert payload["export_status"] == "blocked"
    assert payload["reason_codes"] == ["REVIEW_REQUIRED"]
    assert payload["program_written"] is False
    assert payload["human_approval"] is False
    names = sorted(path.name for path in destination.iterdir())
    assert names == ["candidate_plan.json", "preview.json", "result.json"]
    assert (destination / "candidate_plan.json").exists()
    assert (destination / "preview.json").exists()
    assert not (destination / "program.gcode").exists()
    candidate = json.loads((destination / "candidate_plan.json").read_text(encoding="utf-8"))
    assert candidate["experimental_banner"] == "EXPERIMENTAL — NOT FOR MACHINING"
    assert candidate["program_exported"] is False
    assert candidate["human_approval"] is False
    assert candidate["toolpath"]["version"] == "camstudio_toolpath_v1"
    assert candidate["motion_source"] == "rectangular_centerline_planner"
    preview = json.loads((destination / "preview.json").read_text(encoding="utf-8"))
    assert preview["authoritative"] is False
    assert len(preview["segments"]) == 12
    errors = validate(candidate, load_schema(_SCHEMAS / "traceable_plan_v2.schema.json"))
    assert errors == []
    planner = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    assert validate(planner, load_schema(
        _SCHEMAS / "rectangular_planner_input_v1.schema.json")) == []


def test_reviewed_export_writes_labeled_program(tmp_path):
    package = _package(tmp_path)
    prepared = tmp_path / "prepared"
    prepare_planned_witness(package, prepared, case="rectangle")
    digest = json.loads(
        (prepared / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    exported = tmp_path / "exported"
    # Distinct directory, so copy is not required: export plans again with a review.
    payload = export_planned_witness(
        package, exported, fixture_review_bytes(digest), case="rectangle")
    assert payload["exit_code"] == 0
    assert payload["export_status"] == "written"
    assert payload["program_written"] is True
    assert payload["human_approval"] is False
    program = (exported / "program.gcode").read_bytes()
    text = program.decode("utf-8")
    assert text.startswith("(EXPERIMENTAL — NOT FOR MACHINING)\n")
    manifest = json.loads((exported / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["program_sha256"] == hashlib.sha256(program).hexdigest()
    assert manifest["experimental_banner"] in text
    assert manifest["human_approval"] is False
    assert manifest["operational_export"] is False
    assert manifest["planner_id"] == "creation-studio.rectangle-centerline"
    assert validate(manifest, load_schema(
        _SCHEMAS / "traceable_export_manifest_v2.schema.json")) == []
    candidate = json.loads(
        (exported / "candidate_plan.json").read_text(encoding="utf-8"))
    assert candidate["program_exported"] is False
    assert candidate["plan_digest"] == manifest["plan_digest"]


def test_cli_prepare_and_export_match_the_api(tmp_path):
    package = _package(tmp_path)
    prepare_dir = tmp_path / "cli-prepare"
    completed = _cli([
        "--package", str(package), "--destination", str(prepare_dir),
        "--mode", "prepare", "--case", "rectangle",
    ])
    assert completed.returncode == 1
    body = json.loads(completed.stdout)
    assert body["planning_status"] == "candidate_ready"
    assert body["export_status"] == "blocked"
    assert body["reason_codes"] == ["REVIEW_REQUIRED"]
    digest = json.loads(
        (prepare_dir / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    review = tmp_path / "review.json"
    review.write_bytes(fixture_review_bytes(digest))
    export_dir = tmp_path / "cli-export"
    completed = _cli([
        "--package", str(package), "--destination", str(export_dir),
        "--mode", "export", "--review", str(review), "--case", "rectangle",
    ])
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["program_written"] is True
    assert (export_dir / "program.gcode").read_text(encoding="utf-8").startswith(
        "(EXPERIMENTAL — NOT FOR MACHINING)\n")


def test_verify_mode_ignores_planner_inputs(tmp_path):
    package = _package(tmp_path)
    destination = tmp_path / "verify"
    payload = run_witness(package, destination, case="rectangle")
    assert payload["reason_codes"] == ["UNSUPPORTED_CAPABILITY"]
    assert payload["program_written"] is False
    assert payload["candidate_plan"] is None
    assert not (destination / "candidate_plan.json").exists()
    assert not (destination / "program.gcode").exists()
    completed = _cli([
        "--package", str(package), "--destination", str(tmp_path / "verify-cli"),
        "--case", "rectangle",
    ])
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["reason_codes"] == ["UNSUPPORTED_CAPABILITY"]


def test_foreign_review_and_operational_mode_stay_blocked(tmp_path):
    package = _package(tmp_path)
    destination = tmp_path / "export"
    payload = export_planned_witness(
        package, destination, fixture_review_bytes("a" * 64), case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["PLAN_CHANGED"]
    assert not (destination / "program.gcode").exists()
    assert (destination / "candidate_plan.json").exists()
    verification = verify_package(package)
    from cam_creation_studio.traceability.planner_inputs import load_planner_inputs
    from cam_creation_studio.traceability.planning import build_generated_candidate
    loaded, refusal = load_planner_inputs(
        package, verification.bundle.snapshot.request_raw)
    assert refusal is None and loaded is not None
    candidate, refusal = build_generated_candidate(verification, loaded)
    assert refusal is None and candidate is not None
    operational = evaluate_generated_candidate_export(
        candidate, package, fixture_review_bytes(candidate.plan_digest),
        mode="operational",
    )
    assert operational.allowed is False
    assert operational.refusal.code == "EXPERIMENTAL_ONLY"
    explicit = evaluate_explicit_motion_export(
        build_synthetic_package(tmp_path / "coupon"),
        (make_linear_motion(
            MotionKind.TRAVEL, Point(0, 0, 5), Point(1, 0, 5), index=0),),
        None,
        mode="offline",
    )
    assert explicit.allowed is False


def test_explicit_motion_is_not_relabelled(tmp_path):
    package = build_synthetic_package(tmp_path / "coupon")
    x0, y0, x1, y1 = CENTER
    motions = []
    index = 0
    for depth in (1.0, 2.0):
        z = -depth
        motions.append(make_linear_motion(
            MotionKind.PLUNGE, Point(x0, y0, 5), Point(x0, y0, z),
            index=index, planned_feed_mm_min=300))
        index += 1
        previous = Point(x0, y0, z)
        for corner in (
            Point(x1, y0, z), Point(x1, y1, z), Point(x0, y1, z), Point(x0, y0, z),
        ):
            motions.append(make_linear_motion(
                MotionKind.CUT, previous, corner, index=index,
                planned_feed_mm_min=800))
            index += 1
            previous = corner
        motions.append(make_linear_motion(
            MotionKind.RETRACT, previous, Point(x0, y0, 5), index=index))
        index += 1
    from cam_creation_studio.traceability.service import plan_digest_for
    verification = verify_package(package)
    digest = plan_digest_for(verification, motions)
    evaluation = evaluate_explicit_motion_export(
        package, motions, fixture_review_bytes(digest), mode="offline")
    assert evaluation.allowed
    assert evaluation.manifest["planner_id"] == "unavailable"
    assert evaluation.manifest["motion_source"] == "explicit_linear_motion"
    assert evaluation.manifest["contract_version"] == (
        "creation-studio.traceable-export-manifest/1")
    forged = type("Fake", (), {
        "motion_source": "rectangular_centerline_planner",
        "verification": verification,
    })()
    refused = evaluate_generated_candidate_export(
        forged, package, fixture_review_bytes(digest), mode="offline")
    assert refused.refusal.code == "UNSUPPORTED_CAPABILITY"


def test_input_changes_invalidate_the_review(tmp_path, monkeypatch):
    package = _package(tmp_path)
    first = tmp_path / "first"
    prepare_planned_witness(package, first, case="rectangle")
    original = json.loads(
        (first / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    document = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    document["planned_cut_feed_mm_min"] = CUT_FEED + 50
    (package / "planner-inputs.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    changed = tmp_path / "changed"
    payload = export_planned_witness(
        package, changed, fixture_review_bytes(original), case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["PLAN_CHANGED"]
    assert not (changed / "program.gcode").exists()
    import cam_creation_studio.planning.limits as limits
    monkeypatch.setattr(limits, "PLANNER_VERSION", "2")
    fresh = tmp_path / "fresh"
    write_planned_package(tmp_path / "other")
    prepare_planned_witness(tmp_path / "other", fresh, case="rectangle")
    assert json.loads(
        (fresh / "candidate_plan.json").read_text(encoding="utf-8")
    )["plan_digest"] != original


def test_toctou_refuses_without_a_new_program(tmp_path, monkeypatch):
    package = _package(tmp_path)
    destination = tmp_path / "round"
    prepare_planned_witness(package, destination, case="rectangle")
    digest = json.loads(
        (destination / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    review = fixture_review_bytes(digest)
    raw = (package / "operation_plan.json").read_bytes()
    (package / "operation_plan.json").write_bytes(raw + b"\n")
    calls = []
    monkeypatch.setattr(
        "cam_creation_studio.traceability.planning.expand_rectangular_contour",
        lambda *_args, **_kwargs: calls.append(1),
    )
    payload = export_planned_witness(package, destination, review, case="rectangle")
    assert payload["reason_codes"] == ["SNAPSHOT_CHANGED"]
    assert payload["exit_code"] == 1
    assert calls == []
    assert not (destination / "program.gcode").exists()
    assert not (destination / "candidate_plan.json").exists()
    assert (destination / "result.json").exists()


def test_planner_input_toctou_and_oversized_input(tmp_path):
    package = _package(tmp_path)
    destination = tmp_path / "inputs"
    prepare_planned_witness(package, destination, case="rectangle")
    digest = json.loads(
        (destination / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    blob = (package / "planner-inputs.json").read_bytes()
    (package / "planner-inputs.json").write_bytes(blob.replace(b"800", b"801"))
    payload = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert payload["reason_codes"] == ["SNAPSHOT_CHANGED"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "candidate_plan.json").exists()
    huge = tmp_path / "huge"
    write_planned_package(huge)
    (huge / "planner-inputs.json").write_bytes(b"{" + b" " * (MAX_PLANNER_INPUT_BYTES + 8))
    refused = prepare_planned_witness(huge, tmp_path / "huge-out", case="huge")
    assert refused["reason_codes"] == ["UNSUPPORTED_CAPABILITY"]
    assert not (tmp_path / "huge-out" / "candidate_plan.json").exists()


def test_refusal_after_success_removes_stale_program(tmp_path):
    package = _package(tmp_path)
    destination = tmp_path / "again"
    prepared = prepare_planned_witness(package, tmp_path / "prep", case="rectangle")
    digest = json.loads(
        (tmp_path / "prep" / "candidate_plan.json").read_text(encoding="utf-8")
    )["plan_digest"]
    assert prepared["exit_code"] == 1
    exported = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert exported["exit_code"] == 0
    assert (destination / "program.gcode").exists()
    (package / "operation_plan.json").write_bytes(
        (package / "operation_plan.json").read_bytes() + b" ")
    refused = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert refused["reason_codes"] == ["SNAPSHOT_CHANGED"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    assert not (destination / "candidate_plan.json").exists()
    saved = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert saved["program_written"] is False
    assert saved["reason_codes"] == ["SNAPSHOT_CHANGED"]


def test_tool_mismatch_and_unknown_versions_refuse(tmp_path):
    package = _package(tmp_path)
    other = make_operation_plan(tool_id="endmill_1_8")
    text = operation_plan_to_json(other, indent=2, sort_keys=True) + "\n"
    (package / "operation_plan.json").write_bytes(text.encode("utf-8"))
    document = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    document["definition_id"] = other.definitions[0].id
    document["operation_plan"]["sha256"] = sha256_bytes(text.encode("utf-8"))
    (package / "planner-inputs.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload = prepare_planned_witness(package, tmp_path / "tool", case="tool")
    assert payload["reason_codes"] == ["UNSUPPORTED_CAPABILITY"]
    assert not (tmp_path / "tool" / "candidate_plan.json").exists()
    fresh = _package(tmp_path / "fresh-parent")
    planner = json.loads((fresh / "planner-inputs.json").read_text(encoding="utf-8"))
    planner["contract_version"] = "creation-studio.rectangular-planner-input/9"
    (fresh / "planner-inputs.json").write_text(
        json.dumps(planner, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    version = prepare_planned_witness(fresh, tmp_path / "version", case="version")
    assert version["reason_codes"] == ["UNSUPPORTED_VERSION"]


def test_committed_fixture_matches_the_builder(tmp_path):
    if not _FIXTURE.is_dir():
        pytest.skip("committed fixture is written during this order")
    rebuilt = write_planned_package(tmp_path / "rebuilt")
    for name in (
        "request.json", "proposal.json", "validation.json", "admission.json",
        "geometry.json", "subject.json", "operation_plan.json",
        "planner-inputs.json",
    ):
        assert (rebuilt / name).read_bytes() == (_FIXTURE / name).read_bytes()


def test_output_collision_does_not_delete_captured_inputs(tmp_path):
    package = _package(tmp_path)
    destination = package / "out"
    destination.mkdir()
    plan_bytes = (package / "operation_plan.json").read_bytes()
    consumed = destination / "program.gcode"
    consumed.write_bytes(plan_bytes)
    proposal_bytes = (package / "proposal.json").read_bytes()
    manifest_input = destination / "manifest.json"
    manifest_input.write_bytes(proposal_bytes)
    planner = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    planner["operation_plan"]["package_ref"] = "out/program.gcode"
    (package / "planner-inputs.json").write_text(
        json.dumps(planner, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    request = json.loads((package / "request.json").read_text(encoding="utf-8"))
    for artifact in request["upstream_artifacts"]:
        if artifact["role"] == "proposal":
            artifact["package_ref"] = "out/manifest.json"
    (package / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload = prepare_planned_witness(package, destination, case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert consumed.read_bytes() == plan_bytes
    assert manifest_input.read_bytes() == proposal_bytes
    assert not (destination / "candidate_plan.json").exists()
    assert not (destination / "result.json").exists()
    manifest_only = _package(tmp_path / "manifest-only")
    manifest_dest = manifest_only / "out"
    manifest_dest.mkdir()
    proposal = (manifest_only / "proposal.json").read_bytes()
    manifest_target = manifest_dest / "manifest.json"
    manifest_target.write_bytes(proposal)
    manifest_request = json.loads(
        (manifest_only / "request.json").read_text(encoding="utf-8"))
    for artifact in manifest_request["upstream_artifacts"]:
        if artifact["role"] == "proposal":
            artifact["package_ref"] = "out/manifest.json"
    (manifest_only / "request.json").write_text(
        json.dumps(manifest_request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    manifest_refusal = prepare_planned_witness(
        manifest_only, manifest_dest, case="rectangle")
    assert manifest_refusal["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert manifest_target.read_bytes() == proposal
    assert not (manifest_dest / "candidate_plan.json").exists()
    fresh = _package(tmp_path / "fresh")
    allowed = prepare_planned_witness(fresh, fresh / "witness-out", case="rectangle")
    assert allowed["planning_status"] == "candidate_ready"
    assert (fresh / "operation_plan.json").is_file()
    assert (fresh / "witness-out" / "candidate_plan.json").is_file()
    assert not (fresh / "witness-out" / "program.gcode").exists()


def test_symlink_output_is_not_written_or_deleted(tmp_path):
    package = _package(tmp_path)
    prepared = prepare_planned_witness(package, tmp_path / "prep", case="rectangle")
    assert prepared["planning_status"] == "candidate_ready"
    digest = json.loads(
        (tmp_path / "prep" / "candidate_plan.json").read_text(encoding="utf-8")
    )["plan_digest"]
    destination = tmp_path / "out"
    destination.mkdir()
    unrelated = tmp_path / "unrelated.gcode"
    unrelated.write_text("KEEP\n", encoding="utf-8")
    link = destination / "program.gcode"
    link.symlink_to(unrelated)
    payload = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert unrelated.read_text(encoding="utf-8") == "KEEP\n"
    assert link.is_symlink()
    assert not (destination / "manifest.json").exists()
    assert not (destination / "result.json").exists()
    real = tmp_path / "real-dest"
    real.mkdir()
    marker = real / "marker.txt"
    marker.write_text("KEEP", encoding="utf-8")
    via = tmp_path / "via"
    via.symlink_to(real, target_is_directory=True)
    refused = prepare_planned_witness(package, via, case="rectangle")
    assert refused["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert marker.read_text(encoding="utf-8") == "KEEP"
    assert not (real / "candidate_plan.json").exists()
    assert not (real / "program.gcode").exists()


def test_manifest_publish_failure_records_the_failure(tmp_path, monkeypatch):
    from cam_creation_studio.traceability import service as gate

    package = _package(tmp_path)
    destination = tmp_path / "out"
    prepare_planned_witness(package, destination, case="rectangle")
    previous = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert previous["reason_codes"] == ["REVIEW_REQUIRED"]
    assert previous["program_written"] is False
    digest = json.loads(
        (destination / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    real_replace = gate._replace_file

    def fail_manifest(source: Path, final: Path) -> None:
        if final.name == "manifest.json":
            raise OSError("injected manifest failure")
        real_replace(source, final)

    monkeypatch.setattr(gate, "_replace_file", fail_manifest)
    payload = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["program_written"] is False
    assert payload["export_status"] == "blocked"
    assert payload["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    saved = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert saved["program_written"] is False
    assert saved["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert saved["reason_codes"] != ["REVIEW_REQUIRED"]
    assert [path.name for path in destination.iterdir() if path.name.startswith(".")] == []


def test_publish_failure_invalidates_a_previous_success(tmp_path, monkeypatch):
    from cam_creation_studio.traceability import service as gate

    package = _package(tmp_path)
    destination = tmp_path / "out"
    prepare_planned_witness(package, tmp_path / "prep", case="rectangle")
    digest = json.loads(
        (tmp_path / "prep" / "candidate_plan.json").read_text(encoding="utf-8")
    )["plan_digest"]
    exported = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert exported["program_written"] is True
    assert (destination / "program.gcode").is_file()
    real_replace = gate._replace_file

    def fail_manifest(source: Path, final: Path) -> None:
        if final.name == "manifest.json":
            raise OSError("injected manifest failure")
        real_replace(source, final)

    monkeypatch.setattr(gate, "_replace_file", fail_manifest)
    payload = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert payload["program_written"] is False
    assert payload["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    saved = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert saved["program_written"] is False
    assert saved["reason_codes"] == ["REFERENCE_UNRESOLVED"]


def test_missing_review_file_invalidates_the_previous_program(tmp_path):
    package = _package(tmp_path)
    prepare_dir = tmp_path / "prep"
    completed = _cli([
        "--package", str(package), "--destination", str(prepare_dir),
        "--mode", "prepare", "--case", "rectangle",
    ])
    assert completed.returncode == 1
    digest = json.loads(
        (prepare_dir / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    review = tmp_path / "review.json"
    review.write_bytes(fixture_review_bytes(digest))
    destination = tmp_path / "out"
    exported = _cli([
        "--package", str(package), "--destination", str(destination),
        "--mode", "export", "--review", str(review), "--case", "rectangle",
    ])
    assert exported.returncode == 0
    assert json.loads(exported.stdout)["program_written"] is True
    missing = tmp_path / "missing-review.json"
    again = _cli([
        "--package", str(package), "--destination", str(destination),
        "--mode", "export", "--review", str(missing), "--case", "rectangle",
    ])
    assert again.returncode == 1
    body = json.loads(again.stdout)
    assert body["program_written"] is False
    assert body["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    saved = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert saved["program_written"] is False
    assert saved["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert (destination / "candidate_plan.json").is_file()


def test_unrepresentable_feed_is_a_refusal(tmp_path):
    package = _package(tmp_path)
    document = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    document["planned_cut_feed_mm_min"] = 10**1000
    (package / "planner-inputs.json").write_text(
        json.dumps(document) + "\n", encoding="utf-8")
    payload = prepare_planned_witness(package, tmp_path / "out", case="huge-feed")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["SCHEMA_INVALID"]
    assert "finite number" in payload["detail"]
    plunge = _package(tmp_path / "plunge-parent")
    plunge_document = json.loads(
        (plunge / "planner-inputs.json").read_text(encoding="utf-8"))
    plunge_document["planned_plunge_feed_mm_min"] = 10**1000
    (plunge / "planner-inputs.json").write_text(
        json.dumps(plunge_document) + "\n", encoding="utf-8")
    refused = prepare_planned_witness(plunge, tmp_path / "plunge-out", case="huge-plunge")
    assert refused["reason_codes"] == ["SCHEMA_INVALID"]
    assert "finite number" in refused["detail"]


def test_cli_usage_exits_2(tmp_path):
    package = _package(tmp_path)
    missing = _cli([
        "--package", str(package), "--destination", str(tmp_path / "out"),
        "--mode", "export",
    ])
    assert missing.returncode == 2
    prepare = _cli([
        "--package", str(package), "--destination", str(tmp_path / "out"),
        "--mode", "prepare", "--review", str(package / "request.json"),
    ])
    assert prepare.returncode == 2


# --- Independent review at 964a8de ----------------------------------------


def _reviewed_export(tmp_path: Path) -> tuple[Path, Path, str]:
    package = _package(tmp_path)
    destination = tmp_path / "out"
    prepare_planned_witness(package, tmp_path / "prep", case="rectangle")
    digest = json.loads(
        (tmp_path / "prep" / "candidate_plan.json").read_text(encoding="utf-8")
    )["plan_digest"]
    exported = export_planned_witness(
        package, destination, fixture_review_bytes(digest), case="rectangle")
    assert exported["program_written"] is True
    return package, destination, digest


@pytest.mark.parametrize("name", [
    "program.gcode", "manifest.json", "result.json", "candidate_plan.json",
])
def test_review_file_that_is_an_output_is_not_replaced(tmp_path, name):
    package, destination, digest = _reviewed_export(tmp_path)
    review = destination / name
    review.write_bytes(fixture_review_bytes(digest))
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    payload = export_planned_witness_from_file(
        package, destination, review, case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == ["REFERENCE_UNRESOLVED"]
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


def test_failed_invalidation_leaves_no_stale_success_record(tmp_path, monkeypatch):
    from cam_creation_studio.traceability import service as gate

    package, destination, _digest = _reviewed_export(tmp_path)

    def no_space(destination: Path, files) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(gate, "_publish_files", no_space)
    with pytest.raises(OSError):
        export_planned_witness(package, destination, b"{", case="rectangle")
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    assert not (destination / "result.json").exists()


def _rewrite_plan(package: Path, edit) -> None:
    plan_path = package / "operation_plan.json"
    text = edit(plan_path.read_bytes().decode("utf-8"))
    plan_path.write_bytes(text.encode("utf-8"))
    planner = json.loads((package / "planner-inputs.json").read_text(encoding="utf-8"))
    planner["operation_plan"]["sha256"] = sha256_bytes(text.encode("utf-8"))
    (package / "planner-inputs.json").write_bytes(
        (json.dumps(planner, indent=2, sort_keys=True) + "\n").encode("utf-8"))


@pytest.mark.parametrize(("old", "new", "code"), [
    ('"x": 60.0', '"x": 1' + "0" * 1000, "UNSUPPORTED_CAPABILITY"),
    ('"x": 60.0', '"x": "60"', "UNSUPPORTED_CAPABILITY"),
    ('"z": 0', '"z": false', "UNSUPPORTED_CAPABILITY"),
    ('"target_depth_mm": 2.0', '"target_depth_mm": 1' + "0" * 1000, "SCHEMA_INVALID"),
    ('"stock_allowance_mm": 0.0', '"stock_allowance_mm": 1' + "0" * 1000, "SCHEMA_INVALID"),
])
def test_malformed_operation_plan_numbers_are_refusals(tmp_path, old, new, code):
    package = _package(tmp_path)

    def edit(text: str) -> str:
        assert old in text
        return text.replace(old, new, 1)

    _rewrite_plan(package, edit)
    payload = prepare_planned_witness(package, tmp_path / "out", case="rectangle")
    assert payload["exit_code"] == 1
    assert payload["reason_codes"] == [code]
    assert not (tmp_path / "out" / "candidate_plan.json").exists()


def test_cli_reports_its_mode(tmp_path):
    package = _package(tmp_path)
    completed = _cli([
        "--package", str(package), "--destination", str(tmp_path / "prep"),
        "--mode", "prepare", "--case", "rectangle",
    ])
    assert json.loads(completed.stdout)["mode"] == "prepare"
