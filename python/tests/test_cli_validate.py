"""CLI validate command (CS-007)."""

import io
import json


from cam_creation_studio.cli.main import main

# A clean CNC program: units declared, spindle on, feeds present, footer shutdown.
CLEAN = """\
G21
G90
M3 S12000
G0 Z5
G1 Z-1 F400
G1 X10 Y0 F800
G0 Z5
M5
M30
"""

# Missing units + cut without feed + spindle never starts -> warning/danger.
DIRTY = "G0 Z5\nG1 X5\nM30\n"

# Units declared and spindle on, but one plunge lacks a feed -> a lone WARNING
# (no danger). Used to exercise the --fail-on danger threshold.
WARN_ONLY = "G21\nG90\nM3 S12000\nG0 Z5\nG1 Z-1\nG1 X10 Y0 F800\nG0 Z5\nM5\nM30\n"


def _stdin(monkeypatch, text):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_clean_program_exits_zero(monkeypatch, capsys):
    _stdin(monkeypatch, CLEAN)
    assert main(["validate", "-"]) == 0


def test_dirty_program_exits_one(monkeypatch, capsys):
    _stdin(monkeypatch, DIRTY)
    assert main(["validate", "-"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_validate_json(monkeypatch, capsys):
    _stdin(monkeypatch, DIRTY)
    rc = main(["validate", "-", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["count"] == len(payload["diagnostics"]) >= 1
    assert {"severity", "code", "message", "line"} <= set(payload["diagnostics"][0])


def test_validate_machine_flag(monkeypatch, capsys):
    # An E word on a CNC dialect is foreign -> a cross-dialect diagnostic.
    _stdin(monkeypatch, "G21\nG0 Z5\nG1 X5 E1 F100\nM3 S1\nM30\n")
    rc = main(["validate", "-", "--machine", "genericCnc", "--json"])
    codes = {d["code"] for d in json.loads(capsys.readouterr().out)["diagnostics"]}
    assert "EXTRUDER_WORD_IN_CNC" in codes
    assert rc == 1


def test_validate_fail_on_never_always_exits_zero(monkeypatch, capsys):
    # A program that fails by default still exits 0 under --fail-on never,
    # while the diagnostics are still reported.
    _stdin(monkeypatch, DIRTY)
    assert main(["validate", "-", "--fail-on", "never"]) == 0
    assert "diagnostic(s)" in capsys.readouterr().out


def test_validate_fail_on_danger_ignores_warnings(monkeypatch, capsys):
    # WARN_ONLY produces a warning and no danger; with --fail-on danger that
    # warning no longer forces a non-zero exit, but is still reported.
    _stdin(monkeypatch, WARN_ONLY)
    rc = main(["validate", "-", "--fail-on", "danger", "--json"])
    payload = json.loads(capsys.readouterr().out)
    severities = {d["severity"] for d in payload["diagnostics"]}
    assert "danger" not in severities  # guard: this fixture is warning-only
    assert "warning" in severities
    assert payload["fail_on"] == "danger"
    assert payload["ok"] is True
    assert rc == 0


def test_validate_fail_on_danger_still_fails_on_danger(monkeypatch, capsys):
    # A danger-bearing program fails even under the relaxed --fail-on danger.
    _stdin(monkeypatch, DIRTY)
    assert main(["validate", "-", "--fail-on", "danger"]) == 1


def test_validate_default_fails_on_warning_only(monkeypatch, capsys):
    # Default policy (--fail-on warning): a warning alone is enough to fail.
    _stdin(monkeypatch, WARN_ONLY)
    assert main(["validate", "-"]) == 1


def test_validate_reports_fail_on_in_json(monkeypatch, capsys):
    _stdin(monkeypatch, CLEAN)
    assert main(["validate", "-", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["fail_on"] == "warning"


def test_validate_missing_file_is_file_error(capsys):
    assert main(["validate", "does-not-exist.gcode"]) == 3
    assert "cannot read" in capsys.readouterr().err
