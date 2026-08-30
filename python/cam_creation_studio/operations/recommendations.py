"""Advisory feeds/speeds generation for a bound machining operation (CS-014).

Delegates every machining number to the existing calculator. This module
does not invent DOC, WOC, stepdown, or stepover, and does not treat
``target_depth_mm`` as depth of cut.
"""

from __future__ import annotations

from ..feeds_speeds.calculator import FeedRecommendation, calculate_feeds
from .errors import RecommendationError
from .resolution import RecommendationInputs


def calculate_advisory_feeds(
    inputs: RecommendationInputs,
) -> FeedRecommendation:
    """Call the canonical calculator with resolved catalog inputs.

    Passes tool diameter, flute count, requested ``spindle_rpm``, and
    material id. Passes ``max_rpm`` only when the machine profile has a
    ceiling. Never supplies ``doc_mm``, ``woc_mm``, ``feed_override``, or
    ``max_power_kw``.
    """
    kwargs: dict = {
        "tool_diameter_mm": inputs.tool.diameter_mm,
        "flutes": inputs.tool.flutes,
        "spindle_rpm": inputs.spindle_rpm,
        "material": inputs.material.id,
    }
    if inputs.machine.max_rpm is not None:
        kwargs["max_rpm"] = inputs.machine.max_rpm
    try:
        return calculate_feeds(**kwargs)
    except ValueError as exc:
        raise RecommendationError(str(exc)) from exc
