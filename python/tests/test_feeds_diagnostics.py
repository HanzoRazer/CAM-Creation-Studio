"""CS-003 feeds/speeds extensions: coded diagnostics, chip thinning, MRR, and
advisory power/torque estimates. The core formulas stay covered by
test_feeds_speeds.py."""

import pytest

from cam_creation_studio.feeds_speeds.calculator import FeedsResult, calculate_feeds


def diag_codes(rec):
    return {d.code for d in rec.diagnostics}


def test_advisory_only_always_present():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert "ADVISORY_ONLY" in diag_codes(rec)


def test_feeds_result_alias_preserved():
    assert FeedsResult is calculate_feeds(
        tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05).__class__


def test_rpm_limit_diagnostic():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=24000,
                          chipload=0.05, max_rpm=18000)
    assert "RPM_EXCEEDS_MACHINE_LIMIT" in diag_codes(rec)


def test_chip_thinning_activates_below_half_diameter():
    # WOC at half diameter -> factor 1.0; below half -> factor > 1.0
    at_half = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                              chipload=0.05, woc_mm=3.0)
    below = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                            chipload=0.05, woc_mm=0.5)
    assert at_half.chip_thinning_factor == pytest.approx(1.0)
    assert below.chip_thinning_factor > 1.0


def test_chip_thinning_capped_at_four():
    tiny = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                           chipload=0.05, woc_mm=0.001)
    assert tiny.chip_thinning_factor == 4.0


def test_mrr_and_power_present_with_woc_doc():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.05, woc_mm=2.0, doc_mm=3.0, material="aluminum")
    assert rec.material_removal_rate == pytest.approx(2.0 * 3.0 * rec.feed_rate, rel=1e-6)
    assert rec.spindle_power_kw is not None and rec.spindle_power_kw > 0
    assert rec.spindle_power_hp is not None and rec.torque_nm is not None
    assert rec.power_w == pytest.approx(rec.spindle_power_kw * 1000, rel=1e-6)


def test_mrr_none_without_engagement():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert rec.material_removal_rate is None
    assert rec.spindle_power_kw is None and rec.torque_nm is None
    assert rec.chip_thinning_factor == 1.0


def test_woc_exceeds_diameter_is_danger():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.05, woc_mm=8.0, doc_mm=1.0)
    assert "WOC_EXCEEDS_DIAMETER" in diag_codes(rec)
    assert any(d.code == "WOC_EXCEEDS_DIAMETER" and d.severity == "danger"
               for d in rec.diagnostics)


def test_doc_aggressive_diagnostic():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.05, woc_mm=1.0, doc_mm=9.0)
    assert "DOC_AGGRESSIVE" in diag_codes(rec)


def test_power_limit_diagnostic():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=18000,
                          chipload=0.08, woc_mm=6.0, doc_mm=6.0, material="brass",
                          max_power_kw=0.1)
    assert "POWER_EXCEEDS_MACHINE_LIMIT" in diag_codes(rec)


def test_chipload_high_diagnostic():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.2, material="aluminum")
    assert "CHIPLOAD_HIGH" in diag_codes(rec)


def test_missing_diameter_diagnostic():
    rec = calculate_feeds(tool_diameter_mm=0.0, flutes=2, spindle_rpm=12000, chipload=0.05)
    assert "MISSING_DIAMETER_OR_SPEED" in diag_codes(rec)


def test_diagnostics_serialize():
    rec = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000,
                          chipload=0.05, woc_mm=2.0, doc_mm=3.0)
    d = rec.as_dict()
    assert d["chip_thinning_factor"] == rec.chip_thinning_factor
    assert isinstance(d["diagnostics"], list) and d["diagnostics"][0]["code"]
