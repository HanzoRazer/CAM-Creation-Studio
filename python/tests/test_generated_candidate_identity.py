"""Generated candidate metadata is re-derived from captured inputs.

A digest recomputed from the candidate's own claims is still a claim. These
tests attach that digest, and a fixture review of it, and require refusal
before a program is rendered.
"""

from __future__ import annotations

import json

import pytest
from dataclasses import replace

from cam_creation_studio.traceability.encoding import sha256_bytes
from cam_creation_studio.traceability.parsing import parse_review_bytes
from cam_creation_studio.traceability.planner_inputs import load_planner_inputs
from cam_creation_studio.traceability.planning import (
    build_generated_candidate,
    compute_generated_plan_digest,
    replan_matches,
)
from cam_creation_studio.traceability.review import bind_review
from cam_creation_studio.traceability.service import (
    evaluate_generated_candidate_export,
    export_planned_witness,
    prepare_planned_witness,
    verify_package,
    write_offline_export,
)
from cam_creation_studio.toolpath.serialization import toolpath_to_json
from support.fixture_review import fixture_review_bytes
from support.rectangle_planned import (
    CUT_FEED,
    PLUNGE_FEED,
    TOOL_ID,
    write_planned_package,
)


_FIELDS = (
    ("tool_id", "forged-tool",
     "candidate tool id does not match the reconstructed tool id"),
    ("tool_diameter_mm", 1.0,
     "candidate tool diameter does not match the reconstructed tool diameter"),
    ("tool_flutes", 9,
     "candidate tool flutes does not match the reconstructed tool flutes"),
    ("material_id", "forged-material",
     "candidate material does not match the reconstructed material"),
    ("binding_id", "forged-binding",
     "candidate binding does not match the reconstructed binding"),
    ("definition_id", "forged-definition",
     "candidate definition does not match the reconstructed definition"),
    ("geometry_ids", ("forged-edge",),
     "candidate geometry ids does not match the reconstructed geometry ids"),
    ("planned_cut_feed_mm_min", CUT_FEED + 1,
     "candidate planned cut feed does not match the reconstructed planned cut feed"),
    ("planned_plunge_feed_mm_min", PLUNGE_FEED + 1,
     "candidate planned plunge feed does not match the reconstructed planned plunge feed"),
    ("recommendation_id", "forged-recommendation",
     "candidate recommendation does not match the reconstructed recommendation"),
)


def _load(package):
    verification = verify_package(package)
    assert verification.accepted and verification.bundle is not None
    loaded, refusal = load_planner_inputs(
        package, verification.bundle.snapshot.request_raw)
    assert refusal is None and loaded is not None
    candidate, refusal = build_generated_candidate(verification, loaded)
    assert refusal is None and candidate is not None
    return candidate


def _claim(candidate, **overrides):
    """Recompute the digest from the candidate's own, possibly false, fields."""
    forged = replace(candidate, **overrides)
    digest = compute_generated_plan_digest(
        verification=forged.verification,
        planner_input_sha256=forged.additional.planner_input_sha256,
        operation_plan_sha256=forged.additional.operation_plan_sha256,
        plan=forged.plan,
        definition_id=forged.definition_id,
        binding_id=forged.binding_id,
        geometry_ids=forged.geometry_ids,
        recommendation_id=forged.recommendation_id,
        planned_cut_feed_mm_min=forged.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=forged.planned_plunge_feed_mm_min,
        tool_id=forged.tool_id,
        tool_diameter_mm=forged.tool_diameter_mm,
        tool_flutes=forged.tool_flutes,
        material_id=forged.material_id,
    )
    return replace(forged, plan_digest=digest)


def _refuse_claim(package, candidate, **overrides):
    forged = _claim(candidate, **overrides)
    assert forged.plan_digest != candidate.plan_digest
    review = fixture_review_bytes(forged.plan_digest)
    assert json.loads(review)["plan_digest"] == forged.plan_digest
    assert json.loads(review)["authority"] == "fixture_binding_only"
    refusal = replan_matches(forged)
    evaluation = evaluate_generated_candidate_export(
        forged, package, review, mode="offline")
    return forged, refusal, evaluation


@pytest.mark.parametrize(("field", "value", "detail"), _FIELDS)
def test_each_false_claim_refuses_before_rendering(tmp_path, field, value, detail):
    package = write_planned_package(tmp_path / "rectangle")
    candidate = _load(package)
    assert replan_matches(candidate) is None
    assert getattr(candidate, field) != value
    _forged, refusal, evaluation = _refuse_claim(package, candidate, **{field: value})
    assert refusal is not None
    assert refusal.code == "PLAN_CHANGED"
    assert refusal.detail == detail
    assert evaluation.allowed is False
    assert evaluation.program_text is None
    assert evaluation.refusal is not None
    assert evaluation.refusal.code == "PLAN_CHANGED"
    assert evaluation.refusal.detail == detail
    assert evaluation.refusal.code != "REVIEW_REQUIRED"


def test_self_consistent_false_tool_and_material_still_refuses(tmp_path):
    package = write_planned_package(tmp_path / "rectangle")
    candidate = _load(package)
    forged, refusal, evaluation = _refuse_claim(
        package, candidate, tool_id="forged-tool", material_id="forged-material")
    claimed = compute_generated_plan_digest(
        verification=forged.verification,
        planner_input_sha256=sha256_bytes(forged.additional.planner_input_raw),
        operation_plan_sha256=sha256_bytes(forged.additional.operation_plan_raw),
        plan=forged.plan,
        definition_id=forged.definition_id,
        binding_id=forged.binding_id,
        geometry_ids=forged.geometry_ids,
        recommendation_id=forged.recommendation_id,
        planned_cut_feed_mm_min=forged.planned_cut_feed_mm_min,
        planned_plunge_feed_mm_min=forged.planned_plunge_feed_mm_min,
        tool_id=forged.tool_id,
        tool_diameter_mm=forged.tool_diameter_mm,
        tool_flutes=forged.tool_flutes,
        material_id=forged.material_id,
    )
    assert forged.plan_digest == claimed
    assert forged.tool_id == "forged-tool"
    assert forged.material_id == "forged-material"
    assert refusal is not None and refusal.code == "PLAN_CHANGED"
    assert refusal.detail == (
        "candidate tool id does not match the reconstructed tool id")
    assert evaluation.program_text is None
    assert evaluation.refusal.code == "PLAN_CHANGED"


def test_reconstruction_agrees_with_the_published_candidate(tmp_path):
    from cam_creation_studio.traceability.planning import derive_rectangular_state

    package = write_planned_package(tmp_path / "rectangle")
    candidate = _load(package)
    derived, refusal = derive_rectangular_state(
        candidate.verification,
        candidate.additional.planner_input_raw,
        candidate.additional.operation_plan_raw,
    )
    assert refusal is None and derived is not None
    assert not hasattr(derived, "source_seal")
    for name in (
        "definition_id", "binding_id", "geometry_ids", "recommendation_id",
        "planned_cut_feed_mm_min", "planned_plunge_feed_mm_min",
        "tool_id", "tool_diameter_mm", "tool_flutes", "material_id",
        "plan_digest",
    ):
        assert getattr(candidate, name) == getattr(derived, name)
    assert toolpath_to_json(candidate.plan) == toolpath_to_json(derived.plan)
    assert candidate.tool_id == TOOL_ID
    assert candidate.recommendation_id is None
    assert candidate.planned_cut_feed_mm_min == CUT_FEED
    assert replan_matches(candidate) is None


def test_identity_refusal_clears_a_previous_program(tmp_path):
    package = write_planned_package(tmp_path / "rectangle")
    destination = tmp_path / "exported"
    candidate = _load(package)
    written = export_planned_witness(
        package, destination, fixture_review_bytes(candidate.plan_digest),
        case="rectangle")
    assert written["program_written"] is True
    assert (destination / "program.gcode").is_file()
    assert (destination / "manifest.json").is_file()
    captured = {
        path.name: path.read_bytes()
        for path in package.iterdir() if path.is_file()
    }
    forged = _claim(candidate, tool_id="forged-tool", material_id="forged-material")
    evaluation = evaluate_generated_candidate_export(
        forged, package, fixture_review_bytes(forged.plan_digest), mode="offline")
    assert evaluation.program_text is None
    assert evaluation.refusal.code == "PLAN_CHANGED"
    write_offline_export(destination, evaluation)
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    result = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    assert result["program_written"] is False
    assert result["reason_codes"] == ["PLAN_CHANGED"]
    for name, raw in captured.items():
        assert (package / name).read_bytes() == raw


@pytest.mark.parametrize("name", ["operation_plan.json", "planner-inputs.json"])
def test_changed_source_bytes_stop_before_reconstruction(tmp_path, monkeypatch, name):
    package = write_planned_package(tmp_path / "rectangle")
    destination = tmp_path / "exported"
    prepare_planned_witness(package, destination, case="rectangle")
    digest = json.loads(
        (destination / "candidate_plan.json").read_text(encoding="utf-8"))["plan_digest"]
    review = fixture_review_bytes(digest)
    first = export_planned_witness(package, destination, review, case="rectangle")
    assert first["program_written"] is True
    before = {
        path.name: path.read_bytes()
        for path in package.iterdir() if path.is_file()
    }
    calls = []

    def spy(*_args, **_kwargs):
        calls.append(1)
        raise AssertionError("derive_rectangular_state ran after a snapshot change")

    monkeypatch.setattr(
        "cam_creation_studio.traceability.planning.derive_rectangular_state", spy)
    (package / name).write_bytes(before[name] + b"\n")
    payload = export_planned_witness(package, destination, review, case="rectangle")
    assert payload["reason_codes"] == ["SNAPSHOT_CHANGED"]
    assert payload["program_written"] is False
    assert calls == []
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()
    assert not (destination / "candidate_plan.json").exists()
    for filename, raw in before.items():
        if filename == name:
            continue
        assert (package / filename).read_bytes() == raw


def test_catalog_chipload_change_invalidates_the_old_plan(tmp_path, monkeypatch):
    package = write_planned_package(tmp_path / "rectangle")
    destination = tmp_path / "exported"
    candidate = _load(package)
    review = fixture_review_bytes(candidate.plan_digest)
    written = export_planned_witness(package, destination, review, case="rectangle")
    assert written["program_written"] is True
    import cam_creation_studio.toolpath.builders as builders

    original = builders.resolve_material

    def changed(binding):
        material = original(binding)
        return replace(material, chipload_mm=(material.chipload_mm[0], material.chipload_mm[1] + 0.01))

    monkeypatch.setattr(builders, "resolve_material", changed)
    refusal = replan_matches(candidate)
    assert refusal is not None
    assert refusal.code == "PLAN_CHANGED"
    assert refusal.detail == "candidate plan does not match the reconstructed plan"
    again = export_planned_witness(package, destination, review, case="rectangle")
    assert again["reason_codes"] == ["PLAN_CHANGED"]
    assert again["program_written"] is False
    assert "review is bound to a different plan digest" in again["detail"]
    assert not (destination / "program.gcode").exists()
    assert not (destination / "manifest.json").exists()


def test_version_1_review_does_not_authorize_version_2(tmp_path, monkeypatch):
    import cam_creation_studio.planning.limits as limits
    from cam_creation_studio.traceability.compatibility import policy_digest

    package = write_planned_package(tmp_path / "rectangle")
    monkeypatch.setattr(limits, "PLANNER_VERSION", "1")
    assert policy_digest() != ""
    historical_policy = policy_digest()
    historical = _load(package)
    historical_review = fixture_review_bytes(historical.plan_digest)
    monkeypatch.setattr(limits, "PLANNER_VERSION", "2")
    assert policy_digest() != historical_policy
    refusal = replan_matches(historical)
    assert refusal is not None
    assert refusal.code == "PLAN_CHANGED"
    assert refusal.detail == (
        "candidate plan digest does not match the reconstructed digest")
    evaluation = evaluate_generated_candidate_export(
        historical, package, historical_review, mode="offline")
    assert evaluation.program_text is None
    assert evaluation.refusal.code == "PLAN_CHANGED"
    assert evaluation.refusal.detail == refusal.detail
    current = _load(package)
    review, parse_refusal = parse_review_bytes(historical_review)
    assert parse_refusal is None and review is not None
    bound = bind_review(review, current.plan_digest)
    assert bound is not None
    assert bound.code == "POLICY_UNSUPPORTED"
    assert bound.detail == "review policy digest does not match the local policy"
    destination = tmp_path / "exported"
    payload = export_planned_witness(
        package, destination, fixture_review_bytes(current.plan_digest),
        case="rectangle")
    assert payload["exit_code"] == 0
    assert payload["program_written"] is True
    assert payload["human_approval"] is False
    program = (destination / "program.gcode").read_text(encoding="utf-8")
    assert program.startswith("(EXPERIMENTAL — NOT FOR MACHINING)\n")
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["planner_version"] == "2"
    assert manifest["planner_id"] == "creation-studio.rectangle-centerline"
    assert manifest["human_approval"] is False
    assert manifest["operational_export"] is False
    assert manifest["experimental_banner"] == "EXPERIMENTAL — NOT FOR MACHINING"
