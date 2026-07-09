"""Diagnostic-code alias resolution (DEV ORDER CS-006).

Some legacy codes map to a canonical spec code (e.g. ``EMPTY_PROGRAM_BODY`` ->
``EMPTY_PROGRAM``). Consumers should ask via :func:`has_code` rather than raw
string equality; these tests lock that alias behavior and confirm it is a pure
lookup that never mutates the diagnostics it inspects.
"""

from cam_creation_studio.gcode.validator import codes, has_code, validate_program

# An empty (motion-free) program: the structure rule emits the legacy
# EMPTY_PROGRAM_BODY code, which aliases to canonical EMPTY_PROGRAM.
EMPTY_PROGRAM_TEXT = "G21\n; nothing here\n"


def _empty_diags():
    return validate_program(EMPTY_PROGRAM_TEXT, "genericCnc")


def test_legacy_code_resolves_to_canonical():
    diags = _empty_diags()
    # The legacy code is what is actually emitted...
    assert "EMPTY_PROGRAM_BODY" in {d.code for d in diags}
    # ...yet has_code finds it under the canonical name.
    assert has_code(diags, "EMPTY_PROGRAM")


def test_direct_canonical_match_still_works():
    diags = _empty_diags()
    # A caller asking with the exact emitted (legacy) code also matches.
    assert has_code(diags, "EMPTY_PROGRAM_BODY")
    # And a directly-emitted canonical code matches by its own name.
    real = validate_program("G0 Z5\nG1 X5\nM30\n", "genericCnc")
    assert has_code(real, "CUT_WITHOUT_FEED")
    assert codes.canonical_code("CUT_WITHOUT_FEED") == "CUT_WITHOUT_FEED"


def test_unknown_code_is_false():
    diags = _empty_diags()
    assert has_code(diags, "NO_SUCH_CODE") is False
    # An empty diagnostic set never matches anything.
    assert has_code([], "EMPTY_PROGRAM") is False


def test_alias_resolution_does_not_mutate_diagnostics():
    diags = _empty_diags()
    before = [d.code for d in diags]
    # Resolving through the alias must not rewrite the diagnostics in place.
    has_code(diags, "EMPTY_PROGRAM")
    after = [d.code for d in diags]
    assert after == before == ["EMPTY_PROGRAM_BODY"]


def test_canonical_code_is_a_pure_lookup():
    # Non-legacy codes pass through unchanged; the map itself is not consulted
    # for identity of canonical codes.
    assert codes.canonical_code("EMPTY_PROGRAM") == "EMPTY_PROGRAM"
    assert codes.canonical_code("EMPTY_PROGRAM_BODY") == "EMPTY_PROGRAM"
    assert codes.canonical_code("TOTALLY_UNKNOWN") == "TOTALLY_UNKNOWN"
