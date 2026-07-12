"""CLI feeds command (CS-007)."""

import json

import pytest

from cam_creation_studio.cli.main import main

BASE = ["feeds", "-d", "6", "-n", "2", "-r", "18000"]


def test_feeds_by_material_human(capsys):
    assert main(BASE + ["--material", "aluminum"]) == 0
    out = capsys.readouterr().out
    assert "ADVISORY" in out and "feed rate" in out


def test_feeds_by_chipload_json(capsys):
    assert main(BASE + ["--chipload", "0.05", "--json"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["rpm"] == 18000
    assert rec["feed_rate"] > 0
    assert rec["chipload"] == 0.05


def test_feeds_with_engagement_reports_mrr(capsys):
    assert main(BASE + ["--material", "aluminum", "--woc", "1.5", "--doc", "6",
                        "--json"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["material_removal_rate"] is not None
    assert rec["spindle_power_kw"] is not None


def test_feeds_over_max_rpm_warns(capsys):
    assert main(BASE + ["--material", "aluminum", "--max-rpm", "10000",
                        "--json"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert any("exceeds" in w for w in rec["warnings"])


def test_feeds_requires_material_or_chipload(capsys):
    with pytest.raises(SystemExit) as exc:
        main(BASE)  # neither --material nor --chipload
    assert exc.value.code == 2


def test_feeds_material_and_chipload_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as exc:
        main(BASE + ["--material", "aluminum", "--chipload", "0.05"])
    assert exc.value.code == 2


def test_feeds_bad_flutes_is_usage_error(capsys):
    # flutes=0 passes argparse (an int) but the calculator rejects it -> exit 2.
    assert main(["feeds", "-d", "6", "-n", "0", "-r", "18000",
                 "--chipload", "0.05"]) == 2
    assert "flutes" in capsys.readouterr().err
