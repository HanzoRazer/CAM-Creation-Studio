"""Export preflight — the policy gate at the export boundary (CS-009).

Covers the result contract, each policy rule, the immutability/determinism
invariants, and the CLI's refusal to write a blocked artifact.

The central design claim under test is the blocking/advisory split: preflight
blocks what Creation Studio can *know* is wrong (contradictions, unrepresentable
programs) and only reports what depends on a machine it cannot see. Several
tests below exist specifically to stop that line from drifting.
"""

import json

import pytest

from cam_creation_studio.cli.main import main
from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.gcode.generator import build_program
from cam_creation_studio.gcode.validator import codes
from cam_creation_studio.models import Diagnostic
from cam_creation_studio.safety import DISCLAIMER
from cam_creation_studio.safety.preflight import (
    ALL_RULE_IDS,
    BLOCKING_CODES,
    POLICY_VERSION,
    ExportPreflightResult,
    run_export_preflight,
)
from cam_creation_studio.shared.serialization import from_dict, to_dict, to_json

CNC = {"machine": "genericCnc"}

# A well-formed program: units declared, safe-Z retract, spindle on, feed set,
# clean shutdown. Preflight must find nothing at all here.
CLEAN = "G21\nG90\nM3 S12000\nG0 Z5\nG1 X10 Y10 F800\nG0 Z5\nM5\nM30\n"

JOB = {
    "config": {"machine": "genericCnc", "units": "mm", "positioning": "abs",
               "safeZ": 5, "spindleOn": True, "spindleRpm": 12000},
    "job": {"mode": "manual", "moves": [
        {"type": "G0", "x": 0, "y": 0, "z": 5},
        {"type": "G1", "x": 40, "y": 0, "f": 800},
    ]},
}

# Same job, but the arc carries no I/J center and no R radius — geometry that
# cannot be resolved, so export must be blocked.
BAD_ARC_JOB = {
    "config": dict(JOB["config"]),
    "job": {"mode": "manual", "moves": [
        {"type": "G0", "x": 0, "y": 0, "z": 5},
        {"type": "G2", "x": 40, "y": 0, "f": 800},
    ]},
}


def _write_job(tmp_path, doc, name="job.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def _codes(diags):
    return [d.code for d in diags]


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #
def test_result_is_immutable():
    result = run_export_preflight(CLEAN, CNC)
    with pytest.raises(Exception):
        result.export_allowed = False


def test_result_serializes_through_shared_serializer():
    result = run_export_preflight("G20\nG21\nG0 Z5\nG1 X1 F10\nM30\n", CNC)
    data = to_dict(result)
    assert data["policy_version"] == POLICY_VERSION
    assert data["export_allowed"] is False
    # Diagnostics nest as plain data, and the whole thing is JSON-encodable.
    assert isinstance(data["blocking_findings"][0], dict)
    json.loads(to_json(result))


def test_result_round_trips_through_from_dict():
    original = run_export_preflight(CLEAN, CNC)
    restored = from_dict(ExportPreflightResult, to_dict(original))
    assert restored == original


def test_equal_inputs_produce_equal_results():
    assert run_export_preflight(CLEAN, CNC) == run_export_preflight(CLEAN, CNC)


def test_disclaimer_is_always_present():
    for text in (CLEAN, "", "G20\nG21\nG1 X1 F1\n"):
        assert run_export_preflight(text, CNC).disclaimer == DISCLAIMER


def test_policy_version_is_always_present():
    assert run_export_preflight("", {}).policy_version == POLICY_VERSION
    assert run_export_preflight(CLEAN, CNC).policy_version == POLICY_VERSION


def test_blocking_findings_force_export_disallowed():
    result = run_export_preflight("G20\nG21\nG0 Z5\nG1 X1 F10\nM30\n", CNC)
    assert result.blocking_findings
    assert result.export_allowed is False


def test_advisory_only_findings_permit_export():
    # No spindle start and no feed: both advisory, because whether they matter
    # depends on a machine Creation Studio cannot inspect.
    result = run_export_preflight("G21\nG0 Z5\nG1 X10\nM30\n", CNC)
    assert result.advisory_findings and not result.blocking_findings
    assert result.export_allowed is True


def test_no_findings_permit_export():
    result = run_export_preflight(CLEAN, CNC)
    assert result.findings == ()
    assert result.export_allowed is True


def test_findings_property_lists_blocking_first():
    result = run_export_preflight("G20\nG21\nG0 Z5\nG1 X1\nM30\n", CNC)
    assert result.findings[:len(result.blocking_findings)] == result.blocking_findings


def test_summary_uses_permitted_vocabulary():
    allowed = run_export_preflight(CLEAN, CNC).summary()
    blocked = run_export_preflight("", {}).summary()
    assert "preflight passed" in allowed
    assert "blocked by preflight" in blocked
    for banned in ("safe to run", "machine-ready", "certified", "production-ready"):
        assert banned not in allowed.lower() and banned not in blocked.lower()


# --------------------------------------------------------------------------- #
# Rules — non-finite values
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
def test_non_finite_coordinate_blocks(axis):
    result = run_export_preflight(f"G21\nG0 Z5\nG1 {axis}nan F10\nM30\n", CNC)
    assert codes.EXPORT_NON_FINITE_VALUE in _codes(result.blocking_findings)
    assert result.export_allowed is False


@pytest.mark.parametrize("token", ["inf", "-inf", "infinity", "NaN", "+nan"])
def test_non_finite_spellings_block(token):
    result = run_export_preflight(f"G21\nG0 Z5\nG1 X{token} F10\nM30\n", CNC)
    assert codes.EXPORT_NON_FINITE_VALUE in _codes(result.blocking_findings)


def test_non_finite_feed_blocks():
    result = run_export_preflight("G21\nG0 Z5\nG1 X1 Finf\nM30\n", CNC)
    assert codes.EXPORT_NON_FINITE_VALUE in _codes(result.blocking_findings)


def test_non_finite_in_a_comment_does_not_block():
    # 'infinity' inside a comment is prose, not a parameter.
    result = run_export_preflight(
        "G21\nM3 S1\nG0 Z5 ; travel to infinity\nG1 X1 F10 (nan here too)\nG0 Z5\nM30\n", CNC)
    assert codes.EXPORT_NON_FINITE_VALUE not in _codes(result.blocking_findings)
    assert result.export_allowed is True


def test_non_finite_finding_carries_its_line_number():
    result = run_export_preflight("G21\nG0 Z5\nG1 Xnan F10\nM30\n", CNC)
    finding = next(d for d in result.blocking_findings
                   if d.code == codes.EXPORT_NON_FINITE_VALUE)
    assert finding.line == 3


# --------------------------------------------------------------------------- #
# Rules — feed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("feed", ["0", "-5", "-0.001"])
def test_non_positive_feed_on_feed_move_blocks(feed):
    result = run_export_preflight(f"G21\nG0 Z5\nG1 X1 F{feed}\nM30\n", CNC)
    assert codes.EXPORT_NON_POSITIVE_FEED in _codes(result.blocking_findings)


def test_positive_feed_does_not_block():
    result = run_export_preflight(CLEAN, CNC)
    assert codes.EXPORT_NON_POSITIVE_FEED not in _codes(result.blocking_findings)


def test_rapid_without_feed_does_not_block():
    # G0 needs no F. Only feed moves are examined.
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG0 X10 Y10\nM30\n", CNC)
    assert result.export_allowed is True


def test_zero_feed_on_a_rapid_does_not_block():
    result = run_export_preflight("G21\nM3 S1\nG0 Z5 F0\nM30\n", CNC)
    assert codes.EXPORT_NON_POSITIVE_FEED not in _codes(result.blocking_findings)


def test_absent_feed_stays_advisory_not_blocking():
    # CUT_WITHOUT_FEED is the validator's advisory finding; a *missing* feed is
    # a different thing from a non-positive one and must not be promoted.
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG1 X10\nM30\n", CNC)
    assert codes.CUT_WITHOUT_FEED in _codes(result.advisory_findings)
    assert result.export_allowed is True


# --------------------------------------------------------------------------- #
# Rules — units and dialect
# --------------------------------------------------------------------------- #
def test_unit_mismatch_blocks():
    result = run_export_preflight(
        "G20\nM3 S1\nG0 Z5\nG1 X1 F10\nM30\n", {"machine": "genericCnc", "units": "mm"})
    assert codes.EXPORT_UNIT_MISMATCH in _codes(result.blocking_findings)


def test_unit_agreement_does_not_block():
    result = run_export_preflight(
        "G20\nM3 S1\nG0 Z5\nG1 X1 F10\nM30\n", {"machine": "genericCnc", "units": "in"})
    assert codes.EXPORT_UNIT_MISMATCH not in _codes(result.blocking_findings)


def test_unit_check_is_silent_when_config_declares_no_units():
    result = run_export_preflight("G20\nM3 S1\nG0 Z5\nG1 X1 F10\nM30\n", CNC)
    assert codes.EXPORT_UNIT_MISMATCH not in _codes(result.blocking_findings)


def test_unusable_units_value_is_not_adjudicated_here():
    # A junk units value is a generation-config problem; preflight does not
    # invent a mismatch finding it cannot substantiate.
    result = run_export_preflight(
        "G21\nM3 S1\nG0 Z5\nG1 X1 F10\nM30\n", {"machine": "genericCnc", "units": "furlongs"})
    assert codes.EXPORT_UNIT_MISMATCH not in _codes(result.blocking_findings)


def test_conflicting_unit_declarations_block():
    result = run_export_preflight("G20\nG21\nM3 S1\nG0 Z5\nG1 X1 F10\nM30\n", CNC)
    assert codes.DUPLICATE_UNITS in _codes(result.blocking_findings)


def test_undeclared_units_stays_advisory():
    # Absent units is a real hazard, but it is the operator's to resolve — and
    # blocking on absence is exactly what the order forbids.
    result = run_export_preflight("M3 S1\nG0 Z5\nG1 X1 F10\nM30\n", CNC)
    assert codes.UNITS_NOT_DECLARED in _codes(result.advisory_findings)
    assert result.export_allowed is True


def test_unsupported_dialect_blocks():
    result = run_export_preflight(CLEAN, {"machine": "no-such-machine"})
    assert codes.UNSUPPORTED_DIALECT in _codes(result.blocking_findings)
    assert result.export_allowed is False


def test_unsupported_dialect_is_reported_once():
    # Preflight reclassifies the validator's finding rather than detecting the
    # same condition a second time (CS-009 Decision 1).
    result = run_export_preflight(CLEAN, {"machine": "no-such-machine"})
    assert _codes(result.blocking_findings).count(codes.UNSUPPORTED_DIALECT) == 1
    assert len(result.blocking_findings) == 1


def test_arc_on_non_arc_dialect_blocks():
    result = run_export_preflight("G21\nG0 Z5\nG2 X1 I1 J1 F10\nM30\n", {"machine": "marlin"})
    assert codes.ARC_ON_NON_ARC_DIALECT in _codes(result.blocking_findings)


def test_arc_without_center_or_radius_blocks():
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG2 X1 F10\nM30\n", CNC)
    assert codes.ARC_WITHOUT_CENTER_OR_RADIUS in _codes(result.blocking_findings)


def test_no_machine_named_skips_dialect_rules():
    result = run_export_preflight(CLEAN, {})
    assert codes.UNSUPPORTED_DIALECT not in _codes(result.findings)


# --------------------------------------------------------------------------- #
# Rules — empty artifact
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["", "   ", "\n\n", "\t\n  "])
def test_empty_artifact_blocks(text):
    result = run_export_preflight(text, CNC)
    assert _codes(result.blocking_findings) == [codes.EXPORT_EMPTY_ARTIFACT]
    assert result.export_allowed is False


def test_empty_artifact_reports_skipped_rules_explicitly():
    # Decision 4: dependent checks are named as skipped, not silently omitted.
    result = run_export_preflight("", CNC)
    assert set(result.skipped_rule_ids) == set(ALL_RULE_IDS) - set(result.evaluated_rule_ids)
    assert result.skipped_rule_ids


def test_full_evaluation_skips_nothing():
    result = run_export_preflight(CLEAN, CNC)
    assert result.skipped_rule_ids == ()
    assert result.evaluated_rule_ids == ALL_RULE_IDS


# --------------------------------------------------------------------------- #
# Rules — what must NOT be blocked
# --------------------------------------------------------------------------- #
def test_physical_machine_unknowns_do_not_fabricate_blockers():
    """Unknown travel, workholding, tooling, and firmware never block.

    Creation Studio has no machine profile and has never required one. Blocking
    on what it cannot know would be an implicit machine-authority claim.
    """
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG1 X99999 Y99999 F5000\nG0 Z5\nM30\n", CNC)
    assert result.export_allowed is True
    assert result.blocking_findings == ()


def test_dangerous_but_unknowable_conditions_stay_advisory():
    # Cutting with the spindle never started is DiagnosticSeverity.DANGER, and
    # still advisory: severity does not decide blocking, policy does.
    result = run_export_preflight("G21\nG0 Z5\nG1 X10 F100\nM30\n", CNC)
    assert codes.SPINDLE_OFF_WITH_CUTS in _codes(result.advisory_findings)
    assert result.export_allowed is True
    assert any(d.severity is DiagnosticSeverity.DANGER for d in result.advisory_findings)


def test_missing_optional_metadata_stays_advisory():
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG1 X1 F10\n", CNC)
    assert codes.NO_FOOTER_SHUTDOWN in _codes(result.advisory_findings)
    assert result.export_allowed is True


def test_generic_starter_dialect_notice_is_advisory():
    result = run_export_preflight("G21\nM3 S1\nG0 Z5\nG1 X1 F10\nG99\nM30\n", CNC)
    assert codes.UNKNOWN_GCODE in _codes(result.advisory_findings)
    assert result.export_allowed is True


def test_blocking_code_table_is_a_strict_policy_choice():
    # Locks the split so widening it is a deliberate, reviewable edit that
    # also requires a POLICY_VERSION bump.
    assert BLOCKING_CODES == frozenset({
        codes.DUPLICATE_UNITS,
        codes.ARC_WITHOUT_CENTER_OR_RADIUS,
        codes.ARC_ON_NON_ARC_DIALECT,
        codes.UNSUPPORTED_DIALECT,
        codes.EXPORT_EMPTY_ARTIFACT,
        codes.EXPORT_NON_FINITE_VALUE,
        codes.EXPORT_UNIT_MISMATCH,
        codes.EXPORT_NON_POSITIVE_FEED,
    })


def test_export_codes_are_not_part_of_the_cs003_contract():
    # CS-003 promises exactly eleven canonical validator codes; export-policy
    # codes share the registry without joining that contract.
    assert len(codes.CANONICAL_CODES) == 11
    for code in codes.EXPORT_PREFLIGHT_CODES:
        assert code not in codes.CANONICAL_CODES


# --------------------------------------------------------------------------- #
# Determinism and non-mutation
# --------------------------------------------------------------------------- #
MESSY = (
    "G20\nG21\nG2 X1 F0\nG1 Y2 Fnan\nG99\nG1 Z-1\n"
)


def test_findings_are_stably_ordered_across_runs():
    orders = {tuple(_codes(run_export_preflight(MESSY, CNC).findings)) for _ in range(25)}
    assert len(orders) == 1


def test_findings_are_ordered_by_program_location():
    result = run_export_preflight(MESSY, CNC)
    for bucket in (result.blocking_findings, result.advisory_findings):
        located = [d.line for d in bucket if d.line is not None]
        assert located == sorted(located)
        # Program-wide findings (line is None) come first within their bucket.
        lines = [d.line for d in bucket]
        assert lines == sorted(lines, key=lambda n: (0 if n is None else 1, n or 0))


def test_evaluation_does_not_mutate_the_program():
    text = MESSY
    run_export_preflight(text, CNC)
    assert text == MESSY


def test_evaluation_does_not_mutate_the_context():
    config = {"machine": "genericCnc", "units": "mm"}
    snapshot = dict(config)
    run_export_preflight(MESSY, config)
    assert config == snapshot


def test_evaluation_does_not_mutate_existing_diagnostics():
    before = [d.as_dict() for d in run_export_preflight(MESSY, CNC).findings]
    after = [d.as_dict() for d in run_export_preflight(MESSY, CNC).findings]
    assert before == after


def test_repeated_evaluation_returns_an_equal_result():
    first = run_export_preflight(MESSY, CNC)
    second = run_export_preflight(MESSY, CNC)
    assert first == second
    assert to_dict(first) == to_dict(second)


def test_result_carries_no_timestamp():
    # A timestamp would break equality and destabilize fixtures.
    fields = set(to_dict(run_export_preflight(CLEAN, CNC)))
    assert not any("time" in f or "date" in f for f in fields)


def test_findings_are_diagnostics_not_a_second_model():
    for finding in run_export_preflight(MESSY, CNC).findings:
        assert isinstance(finding, Diagnostic)


# --------------------------------------------------------------------------- #
# CLI export boundary
# --------------------------------------------------------------------------- #
def test_passing_preflight_writes_the_requested_file(tmp_path, capsys):
    out = tmp_path / "part.gcode"
    assert main(["generate", _write_job(tmp_path, JOB), "-o", str(out)]) == 0
    assert "G21" in out.read_text(encoding="utf-8")


def test_passing_preflight_reports_on_stderr_only(tmp_path, capsys):
    assert main(["generate", _write_job(tmp_path, JOB)]) == 0
    captured = capsys.readouterr()
    assert "G21" in captured.out                      # stdout stays pure G-code
    assert "preflight passed" in captured.err
    assert DISCLAIMER in captured.err


def test_blocked_preflight_writes_no_file(tmp_path, capsys):
    out = tmp_path / "part.gcode"
    assert main(["generate", _write_job(tmp_path, BAD_ARC_JOB), "-o", str(out)]) == 1
    assert not out.exists()
    assert "Export blocked by preflight" in capsys.readouterr().err


def test_blocked_preflight_does_not_overwrite_an_existing_file(tmp_path, capsys):
    out = tmp_path / "part.gcode"
    out.write_text("PRIOR CONTENT", encoding="utf-8")
    assert main(["generate", _write_job(tmp_path, BAD_ARC_JOB), "-o", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "PRIOR CONTENT"


def test_blocked_preflight_returns_the_validation_exit_code(tmp_path, capsys):
    # Reuses the existing CLI contract (1 = validation failure) rather than
    # inventing a code that would collide with 3 = file error.
    assert main(["generate", _write_job(tmp_path, BAD_ARC_JOB)]) == 1


def test_blocked_preflight_writes_nothing_to_stdout(tmp_path, capsys):
    main(["generate", _write_job(tmp_path, BAD_ARC_JOB)])
    assert capsys.readouterr().out.strip() == ""


def test_blocked_preflight_displays_both_finding_kinds(tmp_path, capsys):
    main(["generate", _write_job(tmp_path, BAD_ARC_JOB)])
    err = capsys.readouterr().err
    assert "Blocking:" in err
    assert codes.ARC_WITHOUT_CENTER_OR_RADIUS in err
    assert "No G-code was written." in err
    assert DISCLAIMER in err


def test_blocked_preflight_json_reports_without_an_artifact(tmp_path, capsys):
    assert main(["generate", _write_job(tmp_path, BAD_ARC_JOB), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["preflight"]["export_allowed"] is False
    # No "gcode" key: nothing downstream can mistake this for an approved artifact.
    assert "gcode" not in payload


def test_blocked_preflight_json_is_not_written_to_the_output_file(tmp_path, capsys):
    out = tmp_path / "part.gcode"
    assert main(["generate", _write_job(tmp_path, BAD_ARC_JOB), "--json", "-o", str(out)]) == 1
    assert not out.exists()


def test_passing_preflight_json_includes_the_report(tmp_path, capsys):
    assert main(["generate", _write_job(tmp_path, JOB), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "G21" in payload["gcode"]
    assert payload["preflight"]["export_allowed"] is True
    assert payload["preflight"]["policy_version"] == POLICY_VERSION


def test_advisory_only_export_succeeds(tmp_path, capsys):
    # Drop the spindle so the program earns advisories but no blockers.
    doc = {"config": {k: v for k, v in JOB["config"].items() if k != "spindleOn"},
           "job": JOB["job"]}
    out = tmp_path / "part.gcode"
    assert main(["generate", _write_job(tmp_path, doc), "-o", str(out)]) == 0
    assert out.exists()
    assert "Advisory:" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Boundary regressions
# --------------------------------------------------------------------------- #
def test_shipped_examples_still_export(tmp_path, capsys):
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "examples"
    for name in ("cnc-pocket-demo.json", "laser-etch-demo.json"):
        doc = json.loads((root / name).read_text(encoding="utf-8"))
        result = run_export_preflight(build_program(doc["config"], doc["job"]), doc["config"])
        assert result.export_allowed, f"{name}: {_codes(result.blocking_findings)}"


def test_preflight_adds_no_runtime_dependency():
    import cam_creation_studio.safety.preflight as module
    source = pathlib_read(module.__file__)
    for line in source.splitlines():
        if line.startswith("import ") or line.startswith("from "):
            root = line.split()[1].split(".")[0]
            assert root in {"__future__", "re", "dataclasses", "typing", ""}, line


def test_preflight_has_no_toolbox_coupling():
    import cam_creation_studio.safety.preflight as module
    source = pathlib_read(module.__file__).lower()
    for forbidden in ("luthiers", "services.api", "instrument_geometry", "fretboard", "rmos"):
        assert forbidden not in source


def pathlib_read(path):
    import pathlib
    return pathlib.Path(path).read_text(encoding="utf-8")
