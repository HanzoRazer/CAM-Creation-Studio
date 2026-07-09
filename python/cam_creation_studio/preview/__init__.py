"""Neutral preview model: turn moves/etch paths into typed segments.

Re-exports the public preview surface so consumers can import from the package
directly. ``Segment`` is the legacy minimal from/to shape (returned by
``model_from_moves``); ``ToolpathSegment`` is the CS-003 canonical shape
(returned by ``build_toolpath_model``). Both are kept importable for
compatibility.
"""

from .toolpath_model import (  # noqa: F401
    ARC,
    BURN,
    CUT,
    EXTRUDE,
    TRAVEL,
    Segment,
    ToolpathSegment,
    build_toolpath_model,
    infer_burn_mode_from_text,
    model_from_etch_paths,
    model_from_moves,
)

__all__ = [
    "TRAVEL",
    "CUT",
    "BURN",
    "EXTRUDE",
    "ARC",
    "Segment",
    "ToolpathSegment",
    "model_from_moves",
    "model_from_etch_paths",
    "build_toolpath_model",
    "infer_burn_mode_from_text",
]
