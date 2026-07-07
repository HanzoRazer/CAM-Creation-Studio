"""The validator is split into structure/dialect/safety modules that each return
Diagnostics; validate_program merges them. These tests exercise the modules
directly and the merged entry point's new dialect rules."""

from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.gcode.validator import DANGER, Diagnostic, Warning, validate_program
from cam_creation_studio.gcode.validator import dialect, safety, structure
from cam_creation_studio.gcode.validator._context import build_context


def codes(text, machine=None):
    return {d.code for d in validate_program(text, machine)}


def struct_codes(text, machine=None):
    return {d.code for d in structure.check(build_context(text, machine))}


# ---- module isolation ----
def test_structure_module_flags_shape():
    c = struct_codes("G1 X10 F100\n", "genericCnc")
    assert "UNITS_NOT_DECLARED" in c      # no G20/G21
    assert "MISSING_SAFE_Z" in c          # no G0 Z
    assert "NO_FOOTER_SHUTDOWN" in c      # no M2/M30


def test_duplicate_units_flagged():
    c = struct_codes("G20\nG21\nG0 Z5\nG1 X1 F100\nM30\n", "genericCnc")
    assert "DUPLICATE_UNITS" in c


def test_safety_module_only_safety_codes():
    ctx = build_context("G21\nG0 Z5\nG1 X10 Y10\nM30\n", "genericCnc")
    found = {d.code for d in safety.check(ctx)}
    assert "CUT_WITHOUT_FEED" in found
    assert "SPINDLE_OFF_WITH_CUTS" in found
    # structural codes are NOT the safety module's job
    assert "UNITS_NOT_DECLARED" not in found


def test_dialect_module_arc_on_marlin():
    ctx = build_context("G21\nG0 Z5\nG1 X0 Y0 F100\nG2 X10 Y10 I5 J0\nM30\n", "marlin")
    assert {d.code for d in dialect.check(ctx)} == {"ARC_ON_NON_ARC_DIALECT"}


def test_dialect_module_unknown_dialect():
    ctx = build_context("G21\nG0 Z5\nM30\n", "nope")
    assert {d.code for d in dialect.check(ctx)} == {"UNSUPPORTED_DIALECT"}


def test_dialect_module_silent_without_machine():
    ctx = build_context("G21\nG0 Z5\nG2 X1 Y1 I1 J0 F100\nM30\n", None)
    assert dialect.check(ctx) == []


# ---- merged entry point ----
def test_diagnostics_are_typed():
    ds = validate_program("G0 Z5\nG1 X10\n")
    assert all(isinstance(d, Diagnostic) for d in ds)
    assert Warning is Diagnostic
    assert DANGER is DiagnosticSeverity.DANGER


def test_merged_supported_dialect_has_no_dialect_noise():
    assert "UNSUPPORTED_DIALECT" not in codes("G21\nG0 Z5\nG1 X1 F1\nM3 S1\nM30\n", "genericCnc")
