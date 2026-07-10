"""CLI parse and preview commands (CS-007)."""

import io
import json


from cam_creation_studio.cli.main import main

PROGRAM = """\
G21
G0 Z5
G1 Z-1 F400
G1 X30 Y0 F800
G2 X40 Y10 I0 J10 F800
M30
"""


def _stdin(monkeypatch, text=PROGRAM):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_parse_human(monkeypatch, capsys):
    _stdin(monkeypatch)
    assert main(["parse"]) == 0
    out = capsys.readouterr().out
    assert "moves" in out and "Bounds" in out


def test_parse_json_stats(monkeypatch, capsys):
    _stdin(monkeypatch)
    assert main(["parse", "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["moves"] == 4
    assert stats["moves_by_command"] == {"G0": 1, "G1": 2, "G2": 1}
    assert stats["bounds"]["max_x"] == 40.0
    assert stats["toolpath"]["total_distance"] > 0


def test_parse_empty_program_has_null_bounds(monkeypatch, capsys):
    _stdin(monkeypatch, "; just a comment\nM30\n")
    assert main(["parse", "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["moves"] == 0
    assert stats["bounds"] is None


def test_preview_human(monkeypatch, capsys):
    _stdin(monkeypatch)
    assert main(["preview"]) == 0
    out = capsys.readouterr().out
    assert "segment" in out and "distance(mm)" in out


def test_preview_json_summary(monkeypatch, capsys):
    _stdin(monkeypatch)
    assert main(["preview", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["segments"] == 4
    assert set(summary["by_type"]) == {"travel", "cut", "arc"}
    assert summary["by_type"]["cut"]["count"] == 2


def test_preview_empty_program(monkeypatch, capsys):
    _stdin(monkeypatch, "; nothing\nM30\n")
    assert main(["preview"]) == 0
    assert "no motion" in capsys.readouterr().out
