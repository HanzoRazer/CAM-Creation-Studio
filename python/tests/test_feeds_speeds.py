import math

import pytest

from cam_creation_studio.feeds_speeds.calculator import calculate_feeds
from cam_creation_studio.feeds_speeds.materials import get_material, list_materials
from cam_creation_studio.feeds_speeds.tools import get_tool, list_tools
from cam_creation_studio.feeds_speeds.machines import get_machine, list_machines


def test_feed_formula():  # Test 9
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert res.feed_rate == 1200


def test_surface_speed_formula():
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert res.surface_speed == pytest.approx(math.pi * 6.0 * 12000, rel=1e-6)


def test_quarter_inch_tool_normalizes():  # Test 10
    assert get_tool("endmill_1_4").diameter_mm == pytest.approx(6.35, abs=1e-9)


def test_material_chipload_used_when_not_given():
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, material="mdf")
    mat = get_material("mdf")
    assert res.chipload == pytest.approx(mat.chipload_mid, abs=1e-6)


def test_chipload_outside_range_warns():
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.5, material="aluminum")
    assert any("outside" in w for w in res.warnings)


def test_feed_override_reports_computed():
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.05, feed_override=900)
    assert res.feed_rate == 900
    assert any("computed" in n for n in res.notes)


def test_advisory_note_always_present():
    res = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert any("operator verification" in n for n in res.notes)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        calculate_feeds(tool_diameter_mm=6.0, flutes=0, spindle_rpm=12000, chipload=0.05)
    with pytest.raises(ValueError):
        calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000)  # no chipload/material


def test_presets_present():
    assert {m.id for m in list_materials()} >= {"softwood", "hardwood", "mdf", "aluminum"}
    assert {t.id for t in list_tools()} >= {"endmill_1_8", "endmill_1_4", "vbit", "laser_diode"}
    assert {m.id for m in list_machines()} >= {"genericCncRouter", "bcam2030ca_placeholder"}


def test_bcam_placeholder_confirmed_fields_only():
    m = get_machine("bcam2030ca_placeholder")
    assert m.work_area_mm == (2000.0, 3000.0, 200.0)
    assert m.max_rpm == 24000.0
    assert m.specs["spindle"] == "9.0 kW"
    assert m.specs["tool_holder"] == "ISO30"
    assert m.specs["vacuum_pumps"] == "2 x 5.5 kW"
    # Controller dialect is intentionally NOT asserted.
    assert m.suggested_dialect is None
