"""PR #38 review: reconstructed identity and documented deferred limits."""

from dataclasses import replace
import json

import pytest

from cam_creation_studio.traceability.service import evaluate_generated_candidate_export
from cam_creation_studio.traceability.planning import replan_matches
from cam_creation_studio.traceability.parsing import parse_review_bytes
from cam_creation_studio.traceability.review import bind_review
from cam_creation_studio.traceability.compatibility import policy_digest
from support.fixture_review import fixture_review_bytes
from support.rectangle_planned import write_planned_package
from test_generated_candidate_identity import _load


@pytest.mark.parametrize("role", ["planner_input", "operation_plan"])
def test_snapshot_reference_cannot_be_substituted_with_identical_bytes(tmp_path, role):
    package = write_planned_package(tmp_path / "pkg")
    candidate = _load(package)
    name = getattr(candidate.additional, role + "_ref")
    alias = "alias-" + name
    (package / alias).write_bytes((package / name).read_bytes())
    altered = replace(candidate, additional=replace(
        candidate.additional, **{role + "_ref": alias}))
    refusal = replan_matches(altered)
    assert refusal is not None
    assert refusal.code == "PLAN_CHANGED"
    assert "reference" in refusal.detail
    evaluation = evaluate_generated_candidate_export(
        altered, package, fixture_review_bytes(altered.plan_digest), mode="offline")
    assert not evaluation.allowed
    assert evaluation.refusal.code == "PLAN_CHANGED"
    assert evaluation.program_text is None


@pytest.mark.parametrize("plan", [None, "not a plan", {}])
def test_invalid_candidate_plan_refuses_before_motion_projection(tmp_path, monkeypatch, plan):
    package = write_planned_package(tmp_path / "pkg")
    candidate = _load(package)
    altered = replace(candidate, plan=plan)
    calls = []

    def projected(_plan):
        calls.append("projected")
        raise AssertionError("invalid candidate was projected before revalidation")

    monkeypatch.setattr("cam_creation_studio.traceability.service.plan_motions", projected)
    refusal = replan_matches(altered)
    assert refusal is not None and refusal.code == "PLAN_CHANGED"
    evaluation = evaluate_generated_candidate_export(
        altered, package, fixture_review_bytes(candidate.plan_digest), mode="offline")
    assert not evaluation.allowed
    assert evaluation.refusal.code == "PLAN_CHANGED"
    assert evaluation.program_text is None
    assert calls == []


def test_old_policy_review_explains_reprepare_action(tmp_path):
    package = write_planned_package(tmp_path / "pkg")
    candidate = _load(package)
    review, refusal = parse_review_bytes(fixture_review_bytes(
        candidate.plan_digest, policy_digest="0" * 64))
    assert refusal is None
    refused = bind_review(review, candidate.plan_digest)
    assert refused.code == "POLICY_UNSUPPORTED"
    assert "re-prepare" in refused.detail.lower()
    assert "fixture" in refused.detail.lower()


def test_generated_digest_domain_binds_contract_planner_and_policy(tmp_path, monkeypatch):
    import cam_creation_studio.traceability.planning as planning

    captured = []
    original = planning.digest_json

    def capture(payload):
        captured.append(payload)
        return original(payload)

    monkeypatch.setattr(planning, "digest_json", capture)
    candidate = _load(write_planned_package(tmp_path / "pkg"))
    payload = captured[-1]
    assert payload["contract_version"] == "creation-studio.traceable-plan/2"
    assert payload["motion_source"] == "rectangular_centerline_planner"
    assert payload["planner_version"] == "2"
    assert payload["policy_digest"] == policy_digest()
    assert original(payload) == candidate.plan_digest
    for field in ("contract_version", "policy_digest", "planner_version"):
        assert original({**payload, field: "different-domain"}) != candidate.plan_digest


@pytest.mark.parametrize("field", ["planned_cut_feed_mm_min", "planned_plunge_feed_mm_min"])
def test_deferred_finite_feed_range_stays_experimental(tmp_path, field):
    # TODO(CS018-DEFERRED-FEED-RANGE): a physical upper feed limit needs a
    # separately approved policy. This test records current behavior only.
    package = write_planned_package(tmp_path / "pkg")
    path = package / "planner-inputs.json"
    doc = json.loads(path.read_bytes())
    doc[field] = 1e300
    path.write_bytes((json.dumps(doc, sort_keys=True) + "\n").encode("utf-8"))
    candidate = _load(package)
    review = fixture_review_bytes(candidate.plan_digest)
    result = evaluate_generated_candidate_export(candidate, package, review, mode="offline")
    assert result.allowed
    assert result.program_text.startswith("(EXPERIMENTAL — NOT FOR MACHINING)\n")
    assert f"F{int(1e300)}" in result.program_text
    assert result.manifest["human_approval"] is False
    assert result.manifest["operational_export"] is False
    operational = evaluate_generated_candidate_export(candidate, package, review, mode="operational")
    assert not operational.allowed
    assert operational.refusal.code == "EXPERIMENTAL_ONLY"
