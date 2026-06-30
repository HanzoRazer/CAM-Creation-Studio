import pytest

from cam_creation_studio.safety.rules import all_rules, checklist, get_rule, DISCLAIMER
from cam_creation_studio.shared.numbers import (
    parse_number_or_none,
    clamp_number,
    round_for_gcode,
    is_positive_number,
)
from cam_creation_studio.shared.units import mm_to_in, in_to_mm, normalize_units, units_code


# ---- safety ----
def test_safety_rules_present():
    ids = {r.id for r in all_rules()}
    assert {"PREVIEW_NOT_SIMULATION", "VERIFY_GCODE", "FEEDS_ADVISORY", "AIR_CUT"} <= ids


def test_disclaimer_is_advisory():
    assert "educational" in DISCLAIMER.lower()
    assert "not a simulation" in DISCLAIMER.lower()


def test_checklist_tailors_to_machine():
    assert any("spindle" in c.lower() for c in checklist("genericCnc"))
    assert any("laser" in c.lower() for c in checklist("laserGrbl"))


def test_get_rule_unknown_raises():
    with pytest.raises(ValueError):
        get_rule("NOPE")


# ---- numbers ----
def test_parse_number_or_none():
    assert parse_number_or_none("10") == 10
    assert parse_number_or_none("") is None
    assert parse_number_or_none(None) is None
    assert parse_number_or_none("abc") is None
    assert parse_number_or_none(True) is None


def test_round_for_gcode_strips_trailing():
    assert round_for_gcode(10.0) == 10
    assert round_for_gcode(10.123456) == 10.123
    assert isinstance(round_for_gcode(10.0), int)


def test_clamp_and_positive():
    assert clamp_number(5, 0, 3) == 3
    assert clamp_number(-1, 0, 3) == 0
    assert is_positive_number("2.5") and not is_positive_number("0")


# ---- units ----
def test_unit_conversions():
    assert in_to_mm(1) == pytest.approx(25.4)
    assert mm_to_in(25.4) == pytest.approx(1.0)
    assert normalize_units(1, "in", "mm") == pytest.approx(25.4)
    assert normalize_units(5, "mm", "mm") == 5


def test_units_code():
    assert units_code("mm") == "G21"
    assert units_code("in") == "G20"
