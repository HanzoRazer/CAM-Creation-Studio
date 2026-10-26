"""Post already-checked linear motion through the existing G-code generator.

This module does not plan a contour. Callers must already have passed the
shared export gate. Arcs are refused.
"""

from __future__ import annotations

import math

from ..enums import MoveType, Units
from ..gcode.generator import program_to_text
from ..models import GCodeProgram, Move, ProgramFooter, ProgramHeader
from ..shared.numbers import round_for_gcode
from ..safety.preflight import run_export_preflight
from ..toolpath.enums import MotionKind
from ..toolpath.models import ArcMotion, LinearMotion, MotionSegment
from . import codes
from .compatibility import EXPERIMENTAL_BANNER, SUPPORTED_PROFILE
from .encoding import digest_json
from .models import Refusal


def toolpath_digest(motions: tuple[MotionSegment, ...] | list[MotionSegment]) -> str:
    """Digest of explicit motion. Ids and timestamps are omitted."""
    rows = []
    for motion in motions:
        if isinstance(motion, ArcMotion):
            rows.append({
                "clockwise": motion.clockwise,
                "end": [motion.end.x, motion.end.y, motion.end.z],
                "form": "arc",
                "kind": motion.kind.value,
                "planned_feed_mm_min": motion.planned_feed_mm_min,
                "radius": motion.radius,
                "start": [motion.start.x, motion.start.y, motion.start.z],
            })
            continue
        if not isinstance(motion, LinearMotion):
            rows.append({"form": type(motion).__name__})
            continue
        rows.append({
            "end": [motion.end.x, motion.end.y, motion.end.z],
            "form": "linear",
            "kind": motion.kind.value,
            "planned_feed_mm_min": motion.planned_feed_mm_min,
            "start": [motion.start.x, motion.start.y, motion.start.z],
        })
    return digest_json(rows)


def render_experimental_program(
    motions: tuple[MotionSegment, ...] | list[MotionSegment],
    *,
    clearance_mm: float,
) -> tuple[str | None, Refusal | None]:
    """Render linear motion and run the existing export preflight."""
    moves: list[Move] = []
    if not motions:
        return None, Refusal(codes.UNSUPPORTED_CAPABILITY, "no motion to post")
    first = motions[0]
    if isinstance(first, ArcMotion):
        return None, Refusal(
            codes.UNSUPPORTED_CAPABILITY, "arcs are outside this witness")
    moves.append(Move(
        type=MoveType.RAPID,
        x=first.start.x,
        y=first.start.y,
        z=first.start.z,
        comment=EXPERIMENTAL_BANNER,
    ))
    for motion in motions:
        if isinstance(motion, ArcMotion) or not isinstance(motion, LinearMotion):
            return None, Refusal(
                codes.UNSUPPORTED_CAPABILITY, "arcs are outside this witness")
        if motion.kind in (MotionKind.TRAVEL, MotionKind.RETRACT):
            moves.append(Move(
                type=MoveType.RAPID,
                x=motion.end.x,
                y=motion.end.y,
                z=motion.end.z,
            ))
            continue
        if (motion.planned_feed_mm_min is None
                or isinstance(motion.planned_feed_mm_min, bool)
                or not math.isfinite(motion.planned_feed_mm_min)
                or round_for_gcode(motion.planned_feed_mm_min) <= 0):
            return None, Refusal(
                codes.UNSUPPORTED_CAPABILITY,
                "engaging motion is missing a positive planned feed",
            )
        moves.append(Move(
            type=MoveType.LINEAR,
            x=motion.end.x,
            y=motion.end.y,
            z=motion.end.z,
            feed=motion.planned_feed_mm_min,
        ))
    program = GCodeProgram(
        header=ProgramHeader(
            units=Units.MM,
            absolute=True,
            home=False,
            machine="genericCnc",
            safe_z=clearance_mm,
            spindle_on=False,
        ),
        moves=moves,
        footer=ProgramFooter(
            units=Units.MM,
            machine="genericCnc",
            safe_z=clearance_mm,
            spindle_on=False,
            park=True,
        ),
    )
    text = program_to_text(program)
    if not text.endswith("\n"):
        text += "\n"
    marked = f"({EXPERIMENTAL_BANNER})\n" + text
    preflight = run_export_preflight(marked, {
        "machine": "genericCnc",
        "units": "mm",
        "profile": SUPPORTED_PROFILE,
    })
    if not preflight.export_allowed:
        codes_found = ", ".join(item.code for item in preflight.blocking_findings)
        return None, Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            f"existing export preflight blocked the program: {codes_found}",
        )
    return marked, None
