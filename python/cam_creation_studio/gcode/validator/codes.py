"""Canonical validator diagnostic codes (CS-003 contract).

Every diagnostic the validator can emit has a stable string code. Centralizing
them here gives callers a single import to check against and documents the full
vocabulary in one place. The spec-canonical codes are listed first; a handful of
finer-grained codes the rule modules also emit follow.

``LEGACY_ALIASES`` maps older emitted codes to their canonical spec name so a
consumer written against either name resolves the same finding via
:func:`canonical_code` / :func:`has_code`.
"""

from __future__ import annotations

from typing import Iterable

# --- Spec-canonical codes (CS-003 §4 validator contract) ------------------- #
EMPTY_PROGRAM = "EMPTY_PROGRAM"
UNITS_NOT_DECLARED = "UNITS_NOT_DECLARED"
CUT_WITHOUT_FEED = "CUT_WITHOUT_FEED"
ARC_WITHOUT_CENTER_OR_RADIUS = "ARC_WITHOUT_CENTER_OR_RADIUS"
EXTRUDER_WORD_IN_CNC = "EXTRUDER_WORD_IN_CNC"
HEATER_COMMAND_IN_CNC = "HEATER_COMMAND_IN_CNC"
SPINDLE_COMMAND_IN_FDM = "SPINDLE_COMMAND_IN_FDM"
MARLIN_COMMAND_IN_GRBL = "MARLIN_COMMAND_IN_GRBL"
NO_FOOTER_SHUTDOWN = "NO_FOOTER_SHUTDOWN"
MISSING_SAFE_Z = "MISSING_SAFE_Z"
UNKNOWN_GCODE = "UNKNOWN_GCODE"

# --- Finer-grained codes the rule modules also emit ------------------------ #
DUPLICATE_UNITS = "DUPLICATE_UNITS"
EMPTY_PROGRAM_BODY = "EMPTY_PROGRAM_BODY"
UNSUPPORTED_DIALECT = "UNSUPPORTED_DIALECT"
ARC_ON_NON_ARC_DIALECT = "ARC_ON_NON_ARC_DIALECT"
EXTRUSION_WITHOUT_HOTEND = "EXTRUSION_WITHOUT_HOTEND"
NEGATIVE_Z_IN_LASER_MODE = "NEGATIVE_Z_IN_LASER_MODE"
SPINDLE_OFF_WITH_CUTS = "SPINDLE_OFF_WITH_CUTS"

# The eleven canonical codes CS-003 promises, in spec order.
CANONICAL_CODES = (
    EMPTY_PROGRAM,
    UNITS_NOT_DECLARED,
    CUT_WITHOUT_FEED,
    ARC_WITHOUT_CENTER_OR_RADIUS,
    EXTRUDER_WORD_IN_CNC,
    HEATER_COMMAND_IN_CNC,
    SPINDLE_COMMAND_IN_FDM,
    MARLIN_COMMAND_IN_GRBL,
    NO_FOOTER_SHUTDOWN,
    MISSING_SAFE_Z,
    UNKNOWN_GCODE,
)

# Older emitted code -> canonical spec code. The structure module still emits
# EMPTY_PROGRAM_BODY (kept for back-compat); it resolves to EMPTY_PROGRAM here.
LEGACY_ALIASES = {
    EMPTY_PROGRAM_BODY: EMPTY_PROGRAM,
}


def canonical_code(code: str) -> str:
    """Resolve a possibly-legacy code to its canonical spec name."""
    return LEGACY_ALIASES.get(code, code)


def has_code(diagnostics: Iterable, code: str) -> bool:
    """True if any diagnostic carries ``code`` (legacy aliases resolved)."""
    target = canonical_code(code)
    return any(canonical_code(getattr(d, "code", d)) == target for d in diagnostics)
