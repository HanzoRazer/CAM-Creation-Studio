import json

from cam_creation_studio.handoff.handoff import (
    Handoff,
    parse_handoff,
    handoff_text,
    apply_handoff_to_config,
)

HANDOFF = Handoff(rpm=18000, feed=1200, units="mm", material="MDF")


def test_parse_valid():
    raw = json.dumps({"rpm": 18000, "feed": 1200, "units": "mm", "material": "MDF"})
    assert parse_handoff(raw) == HANDOFF


def test_parse_invalid_returns_none():
    assert parse_handoff(None) is None
    assert parse_handoff("{not json") is None
    assert parse_handoff(json.dumps({"feed": 1200})) is None  # no rpm


def test_handoff_text():
    assert handoff_text(HANDOFF) == "S18000 RPM | F1200 mm/min | MDF"
    assert handoff_text(Handoff(rpm=12000, feed=30, units="in")) == "S12000 RPM | F30 in/min"
    assert handoff_text(None) == ""


def test_apply_sets_cnc_and_values():
    cfg = {"machine": "marlin", "units": "in", "moves": []}
    patch = apply_handoff_to_config(cfg, HANDOFF)
    assert patch["machine"] == "genericCnc"
    assert patch["spindleRpm"] == "18000"
    assert patch["etchFeed"] == "1200"
    assert patch["units"] == "mm"


def test_apply_fills_missing_cut_feeds_only():
    cfg = {"moves": [
        {"id": 1, "type": "G0", "x": "0", "f": ""},
        {"id": 2, "type": "G1", "x": "40", "f": ""},
        {"id": 3, "type": "G1", "x": "40", "f": "800"},
        {"id": 4, "type": "G2", "x": "0", "f": "0"},
    ]}
    moves = apply_handoff_to_config(cfg, HANDOFF)["moves"]
    assert moves[0]["f"] == ""       # G0 rapid untouched
    assert moves[1]["f"] == "1200"   # missing feed filled
    assert moves[2]["f"] == "800"    # existing feed kept
    assert moves[3]["f"] == "1200"   # zero feed filled


def test_apply_does_not_mutate_input():
    cfg = {"moves": [{"id": 1, "type": "G1", "x": "1", "f": ""}]}
    before = json.dumps(cfg)
    apply_handoff_to_config(cfg, HANDOFF)
    assert json.dumps(cfg) == before
