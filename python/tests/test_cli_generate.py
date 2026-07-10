"""CLI generate command (CS-007)."""

import io
import json


from cam_creation_studio.cli.main import main

JOB = {
    "config": {"machine": "genericCnc", "units": "mm", "positioning": "abs",
               "safeZ": 5, "spindleOn": True, "spindleRpm": 12000},
    "job": {"mode": "manual", "moves": [
        {"type": "G0", "x": 0, "y": 0, "z": 5},
        {"type": "G1", "x": 40, "y": 0, "f": 800},
    ]},
}


def _write_job(tmp_path, doc=JOB):
    p = tmp_path / "job.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_generate_from_file_to_stdout(tmp_path, capsys):
    assert main(["generate", _write_job(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "G21" in out and "G1 X40" in out


def test_generate_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(JOB)))
    assert main(["generate", "-"]) == 0
    assert "G21" in capsys.readouterr().out


def test_generate_json_wraps_gcode(tmp_path, capsys):
    assert main(["generate", _write_job(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "gcode" in payload and "G21" in payload["gcode"]


def test_generate_output_to_file(tmp_path, capsys):
    out_path = tmp_path / "out.gcode"
    assert main(["generate", _write_job(tmp_path), "-o", str(out_path)]) == 0
    assert capsys.readouterr().out.strip() == ""  # nothing to stdout
    assert "G21" in out_path.read_text(encoding="utf-8")


def test_machine_override_changes_dialect(tmp_path, capsys):
    # Overriding to marlin should change the emitted startup (no spindle M3).
    base = main(["generate", _write_job(tmp_path)])
    assert base == 0
    default_out = capsys.readouterr().out

    assert main(["generate", _write_job(tmp_path), "--machine", "marlin"]) == 0
    marlin_out = capsys.readouterr().out
    assert marlin_out != default_out


def test_generate_missing_job_key_is_usage_error(tmp_path, capsys):
    bad = _write_job(tmp_path, {"config": {}})
    assert main(["generate", bad]) == 2
    assert "job" in capsys.readouterr().err


def test_generate_invalid_json_is_usage_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not valid"))
    assert main(["generate", "-"]) == 2
    assert "invalid JSON" in capsys.readouterr().err
