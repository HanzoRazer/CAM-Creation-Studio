"""Legacy compatibility aliases stay importable and resolve to canonical types.

The CS-003 refactor renamed several public symbols and kept the old names as
aliases (DEV ORDER CS-006, Decision 2). Downstream code imports the old names,
so these must keep resolving — ideally to the *same* object as the canonical
name, not a divergent shim.
"""


def test_feeds_result_alias_resolves_to_feed_recommendation():
    from cam_creation_studio.feeds_speeds import FeedRecommendation, FeedsResult
    assert FeedsResult is FeedRecommendation


def test_machine_alias_resolves_to_machine_profile():
    from cam_creation_studio.feeds_speeds import Machine, MachineProfile
    assert Machine is MachineProfile


def test_warning_alias_resolves_to_diagnostic():
    from cam_creation_studio.gcode.validator import Diagnostic, Warning
    assert Warning is Diagnostic


def test_segment_and_toolpath_segment_importable():
    from cam_creation_studio.preview import Segment, ToolpathSegment
    # Distinct canonical types (minimal vs richer shape), both public.
    assert Segment is not ToolpathSegment
    assert isinstance(Segment, type) and isinstance(ToolpathSegment, type)


def test_legacy_model_from_moves_importable():
    from cam_creation_studio.preview import model_from_moves
    assert callable(model_from_moves)


def test_canonical_names_still_importable():
    # The canonical names remain the primary public surface.
    from cam_creation_studio.feeds_speeds import (  # noqa: F401
        FeedRecommendation,
        MachineProfile,
    )
    from cam_creation_studio.gcode.validator import Diagnostic  # noqa: F401
    from cam_creation_studio.preview import (  # noqa: F401
        ToolpathSegment,
        build_toolpath_model,
    )
