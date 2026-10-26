"""PR #33 review regressions: contracts and checked/posted motion agree."""

from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from cam_creation_studio.cli.main import main
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.fingerprint import strategy_fingerprint
from cam_creation_studio.toolpath.models import ToolpathStrategy
from cam_creation_studio.traceability.bounds import check_declared_request, check_motions
from cam_creation_studio.traceability.compatibility import EXPERIMENTAL_BANNER
from cam_creation_studio.traceability.encoding import sha256_bytes
from cam_creation_studio.traceability.errors import TraceabilityDefect
from cam_creation_studio.traceability.models import VerificationResult
from cam_creation_studio.traceability.parsing import parse_request_bytes
from cam_creation_studio.traceability.service import (
    classify_generate_document,
    evaluate_explicit_motion_export,
    plan_digest_for,
    verify_package,
    write_offline_export,
)
from test_traceable_planning import _good_motions, _package, _review

_REPO = Path(__file__).resolve().parents[2]


def _validator(name):
    # Optional dev dependency: only the schema tests skip without it.
    Draft202012Validator = pytest.importorskip("jsonschema").Draft202012Validator
    schema = json.loads((_REPO / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_published_request_schema_accepts_real_fixture_and_rejects_relabel(tmp_path):
    package = _package(tmp_path)
    body = json.loads((package / "request.json").read_bytes())
    validator = _validator("traceable_planning_request_v1.schema.json")
    validator.validate(body)
    body["workflow_origin"] = "human_authored"
    assert not validator.is_valid(body)
    request, refusal = parse_request_bytes(json.dumps(body).encode())
    assert request is None
    assert refusal.code == "PROVENANCE_IMMUTABLE"


@pytest.mark.parametrize("object_path", [
    ("operation", "centerline"), ("tooling",), ("strategy",),
    ("removal_region",), ("upstream_artifacts", 0),
])
def test_request_schema_rejects_unknown_nested_fields(tmp_path, object_path):
    body = json.loads((_package(tmp_path) / "request.json").read_bytes())
    target = body
    for key in object_path:
        target = target[key]
    target["unexpected"] = True
    assert not _validator("traceable_planning_request_v1.schema.json").is_valid(body)
    assert parse_request_bytes(json.dumps(body).encode())[1].code == "SCHEMA_INVALID"


def test_published_export_and_plan_schemas_validate_actual_payloads(tmp_path, monkeypatch):
    package = _package(tmp_path)
    verification = verify_package(package)
    motions = _good_motions()
    import cam_creation_studio.traceability.planning as planning
    original = planning.digest_json
    captured = []

    def capture(payload):
        captured.append(payload)
        return original(payload)

    monkeypatch.setattr(planning, "digest_json", capture)
    digest = plan_digest_for(verification, motions)
    plan = captured[-1]
    _validator("traceable_plan_v1.schema.json").validate(plan)
    result = evaluate_explicit_motion_export(package, motions, _review(digest), mode="offline")
    assert result.allowed
    _validator("traceable_export_manifest_v1.schema.json").validate(result.manifest)
    result.manifest["review"]["execution_authorized"] = True
    assert not _validator("traceable_export_manifest_v1.schema.json").is_valid(result.manifest)


@pytest.mark.parametrize("variant", ["crlf", "utf16", "bom", "whitespace"])
def test_external_artifact_hash_is_raw_bytes_not_reserialized(tmp_path, variant):
    package = _package(tmp_path)
    artifact = package / "proposal.json"
    raw = artifact.read_bytes()
    changed = {
        "crlf": raw.replace(b"\n", b"\r\n"),
        "utf16": raw.decode().encode("utf-16"),
        "bom": b"\xef\xbb\xbf" + raw,
        "whitespace": json.dumps(json.loads(raw), separators=(",", ":")).encode(),
    }[variant]
    assert sha256_bytes(changed) != sha256_bytes(raw)
    artifact.write_bytes(changed)
    assert verify_package(package).refusal.code == "DIGEST_MISMATCH"


def test_depth_level_comparison_tolerates_arithmetic_only(tmp_path):
    request = replace(verify_package(_package(tmp_path)).request,
                      depth_levels_mm=(0.3,), removal_max_depth_mm=1.0)
    original = _good_motions()[:7]
    # 0.1 + 0.2 is a different float from 0.3.
    depth = 0.1 + 0.2
    motions = tuple(replace(m, start=replace(m.start, z=-depth) if m.start.z < 0 else m.start,
                           end=replace(m.end, z=-depth) if m.end.z < 0 else m.end)
                    for m in original)
    assert check_motions(request, motions) is None
    # No epsilon is allowed to increase the hard maximum material removal.
    limited = replace(request, removal_max_depth_mm=0.3)
    assert check_motions(limited, motions).code == "DEPTH_LIMIT_EXCEEDED"
    off_level = replace(request, depth_levels_mm=(0.299,))
    assert check_motions(off_level, motions).code == "DEPTH_LIMIT_EXCEEDED"


@pytest.mark.parametrize("variant", ["gap", "diagonal_plunge", "diagonal_retract",
                                         "nan", "infinity", "low_initial", "low_final"])
def test_unchecked_or_unsupported_motion_is_refused(tmp_path, variant):
    package = _package(tmp_path)
    motions = list(_good_motions())
    if variant == "gap":
        motions[2] = replace(motions[2], start=Point(999, 999, -1))
    elif variant == "diagonal_plunge":
        motions[1] = replace(motions[1], end=replace(motions[1].end, x=21))
    elif variant == "diagonal_retract":
        motions[6] = replace(motions[6], end=replace(motions[6].end, x=999))
    elif variant in ("nan", "infinity"):
        motions[0] = replace(motions[0], start=Point(math.nan if variant == "nan" else math.inf, 15, 6))
    elif variant == "low_initial":
        motions = motions[1:]
        motions[0] = replace(motions[0], start=replace(motions[0].start, z=0))
    else:
        motions = motions[:6]
    result = evaluate_explicit_motion_export(package, motions, None, mode="offline")
    assert not result.allowed
    assert result.program_text is None
    assert result.refusal.code in {"UNSUPPORTED_CAPABILITY", "CLEARANCE_VIOLATION"}


def test_posted_coordinate_rounding_cannot_escape_removal_region(tmp_path):
    # Exact cutter disk fits, but rounding X from 20.0004 to 20 makes it cross
    # a deliberately tight left boundary by 0.0003 mm.
    from cam_creation_studio.traceability.bounds import check_posting_precision
    request = verify_package(_package(tmp_path)).request
    motions = tuple(replace(m, start=replace(m.start, x=m.start.x + 0.0004),
                           end=replace(m.end, x=m.end.x + 0.0004)) for m in _good_motions())
    request = replace(request, removal_x_min_mm=16.9503,
                      center_x_min_mm=request.center_x_min_mm + 0.0004,
                      center_x_max_mm=request.center_x_max_mm + 0.0004)
    assert check_motions(request, motions) is None
    assert check_posting_precision(request, motions).code == "REMOVAL_BOUND_EXCEEDED"


def test_plan_digest_rejects_missing_verification_even_when_python_is_optimized():
    invalid = VerificationResult(False, None, None, None, None)
    with pytest.raises(TraceabilityDefect, match="verified request"):
        plan_digest_for(invalid, ())


@pytest.mark.parametrize("field", ["frame_name", "strategy_id"])
def test_request_identity_changes_invalidate_plan_review(tmp_path, field):
    verification = verify_package(_package(tmp_path))
    digest = plan_digest_for(verification, _good_motions())
    changed = replace(verification, request=replace(verification.request, **{field: "changed"}))
    assert plan_digest_for(changed, _good_motions()) != digest


@pytest.mark.parametrize("container", [None, "config", "job"])
def test_namespaced_provenance_cannot_fall_through_to_manual_generate(tmp_path, capsys, container):
    doc = {"config": {"units": "mm", "safeZ": 5}, "job": {"mode": "manual", "moves": []}}
    target = doc if container is None else doc[container]
    target["traceability"] = {"workflow_origin": "imported"}
    target["workflow_origin"] = "human_authored"
    assert classify_generate_document(doc) == "provenance_stripped"
    path = tmp_path / "job.json"
    path.write_text(json.dumps(doc))
    output = tmp_path / "out.gcode"
    assert main(["generate", str(path), "-o", str(output)]) == 1
    assert not output.exists()
    assert "PROVENANCE_IMMUTABLE" in capsys.readouterr().err


def test_generic_admission_metadata_is_ordinary_but_artifact_identity_is_governed():
    assert classify_generate_document({"job": {"admission": "operator note"}}) == "ordinary"
    assert classify_generate_document({"job": {"admission": {"description": "note"}}}) == "ordinary"
    assert classify_generate_document({"job": {"admission": {"contract_version": "unknown"}}}) == "governed"
    assert classify_generate_document({"contract_version": "creation-studio.traceable-planning-request/99"}) == "governed"


def test_duplicate_origin_cannot_be_erased_before_classification(tmp_path, capsys):
    path = tmp_path / "job.json"
    path.write_text('{"workflow_origin":"imported", "workflow_origin":"human_authored",'
                    '"job":{"mode":"manual","moves":[]}}')
    output = tmp_path / "out.gcode"
    assert main(["generate", str(path), "-o", str(output)]) != 0
    assert not output.exists()
    assert "duplicate key" in capsys.readouterr().err


def test_malformed_nested_and_overflowing_inputs_are_refusals(tmp_path):
    request = json.loads((_package(tmp_path) / "request.json").read_bytes())
    request["stock"]["x_mm"] = 10 ** 1000
    assert parse_request_bytes(json.dumps(request).encode())[1].code == "SCHEMA_INVALID"
    raw = b'{"extra":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'
    assert parse_request_bytes(raw)[1].code == "SCHEMA_INVALID"


def test_offline_writer_preserves_labels_byte_digest_and_refusal_audit(tmp_path):
    package = _package(tmp_path / "pkg")
    motions = _good_motions()
    digest = plan_digest_for(verify_package(package), motions)
    result = evaluate_explicit_motion_export(package, motions, _review(digest), mode="offline")
    assert result.allowed
    out = tmp_path / "out"
    write_offline_export(out, result)
    assert (out / "program.gcode").read_bytes() == result.program_text.encode("utf-8")
    manifest = json.loads((out / "manifest.json").read_bytes())
    assert sha256_bytes((out / "program.gcode").read_bytes()) == manifest["program_sha256"]
    assert manifest["experimental_banner"] == EXPERIMENTAL_BANNER
    assert json.loads((out / "result.json").read_bytes())["program_written"]
    refused = evaluate_explicit_motion_export(package, motions, _review(digest), mode="operational")
    write_offline_export(out, refused)
    assert not (out / "program.gcode").exists()
    assert not (out / "manifest.json").exists()
    audit = json.loads((out / "result.json").read_bytes())
    assert audit["reason_codes"] == ["EXPERIMENTAL_ONLY"]
    assert audit["experimental_banner"] == EXPERIMENTAL_BANNER
    assert not audit["program_written"]


def test_writer_detects_formatter_label_loss(tmp_path):
    package = _package(tmp_path / "pkg")
    motions = _good_motions()
    digest = plan_digest_for(verify_package(package), motions)
    result = evaluate_explicit_motion_export(package, motions, _review(digest), mode="offline")
    altered = replace(result, program_text=result.program_text.replace(EXPERIMENTAL_BANNER, ""))
    with pytest.raises(TraceabilityDefect, match="label or digest"):
        write_offline_export(tmp_path / "out", altered)
    assert not (tmp_path / "out" / "program.gcode").exists()


# --- Merge-readiness review at dfd8b99 ------------------------------------


def _with_excursion(far):
    """Good contour with a level cut above the stock top, below clearance."""
    good = list(_good_motions())
    first = good[0]
    above = first.end
    low = Point(above.x, above.y, 0.5)
    leg = Point(far[0], far[1], 0.5)

    def move(kind, start, end):
        return replace(first, kind=kind, start=start, end=end, planned_feed_mm_min=500.0)

    excursion = [move(MotionKind.PLUNGE, above, low), move(MotionKind.CUT, low, leg),
                 move(MotionKind.CUT, leg, low), move(MotionKind.RETRACT, low, above)]
    return [first] + excursion + good[1:]


def test_cut_below_clearance_cannot_leave_the_removal_region(tmp_path):
    # Reviewed, so the refusal comes from the motion check and not the review gate.
    package = _package(tmp_path)
    motions = _with_excursion((500.0, 500.0))
    review = _review(plan_digest_for(verify_package(package), motions))
    result = evaluate_explicit_motion_export(package, motions, review, mode="offline")
    assert not result.allowed
    assert result.program_text is None
    assert result.refusal.code == "REMOVAL_BOUND_EXCEEDED"


def test_cut_above_stock_inside_the_removal_region_is_still_checked_not_refused(tmp_path):
    verification = verify_package(_package(tmp_path))
    start = _good_motions()[0].end
    assert check_motions(verification.request, _with_excursion((start.x + 5.0, start.y))) is None


def test_declared_removal_region_must_lie_on_the_stock(tmp_path):
    request = verify_package(_package(tmp_path)).request
    assert check_declared_request(request) is None
    off_stock = replace(
        request, removal_x_min_mm=500.0, removal_x_max_mm=600.0,
        removal_y_min_mm=500.0, removal_y_max_mm=600.0,
        center_x_min_mm=520.0, center_x_max_mm=580.0,
        center_y_min_mm=520.0, center_y_max_mm=580.0)
    assert check_declared_request(off_stock).code == "REMOVAL_BOUND_EXCEEDED"
    negative = replace(request, removal_x_min_mm=-1.0)
    assert check_declared_request(negative).code == "REMOVAL_BOUND_EXCEEDED"


@pytest.mark.parametrize(("strategy", "cs016_fingerprint"), [
    (ToolpathStrategy(travel_height_mm=5.0), "strat-515fe3fce9055a2986400477114b9fe3"),
    (ToolpathStrategy(stepdown_mm=1.5, stepover_mm=2.0, travel_height_mm=5.0),
     "strat-3c2afabf15385cba86068f3504793dd1"),
    (ToolpathStrategy(stepdown_mm=1, travel_height_mm=5),
     "strat-a41285012cab55cc93e78ec7e8c84d3b"),
])
def test_strategies_without_depth_levels_keep_their_cs016_fingerprint(strategy, cs016_fingerprint):
    # Values recorded from main at a2f445e. A change here invalidates every
    # stored toolpath plan.
    assert strategy_fingerprint(strategy) == cs016_fingerprint


def _manual_job():
    return json.loads((_REPO / "examples" / "cnc-pocket-demo.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("variant", ["oversize", "duplicate_key", "nan"])
def test_ordinary_generate_keeps_its_pre_traceability_parsing(tmp_path, variant):
    body = json.dumps(_manual_job())
    if variant == "oversize":
        job = _manual_job()
        job["config"]["_note"] = "x" * 300_000
        body = json.dumps(job)
    elif variant == "duplicate_key":
        body = '{"_note": 1, "_note": 2, ' + body[1:]
    else:
        body = '{"_note": NaN, ' + body[1:]
    path = tmp_path / "job.json"
    path.write_text(body, encoding="utf-8")
    output = tmp_path / "out.gcode"
    assert main(["generate", str(path), "-o", str(output)]) == 0
    assert output.exists()


@pytest.mark.parametrize("variant", ["oversize", "nan", "duplicate_job"])
def test_governed_generate_keeps_strict_parsing(tmp_path, capsys, variant):
    job = _manual_job()
    if variant == "duplicate_job":
        # The later "job" would hide the marker in the first one.
        body = ('{"job": {"traceability": {}}, '
                + json.dumps(job)[1:])
    else:
        job["job"]["traceability"] = {"workflow_origin": "imported"}
        if variant == "oversize":
            job["config"]["_note"] = "x" * 300_000
            body = json.dumps(job)
        else:
            body = '{"_note": NaN, ' + json.dumps(job)[1:]
    path = tmp_path / "job.json"
    path.write_text(body, encoding="utf-8")
    output = tmp_path / "out.gcode"
    assert main(["generate", str(path), "-o", str(output)]) != 0
    assert not output.exists()
    assert "invalid JSON generate document" in capsys.readouterr().err
