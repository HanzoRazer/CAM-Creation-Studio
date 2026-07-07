"""Pure G-code generation — orchestration only.

The actual construction of each section lives in :mod:`header`, :mod:`body`, and
:mod:`footer`. This module just composes them into a whole program, in two ways:

* :func:`build_program` — the dict adapter (config + job mappings), preserved so
  existing callers and the browser-prototype behavior stay identical.
* :func:`program_to_text` — the object path, rendering a typed
  :class:`~cam_creation_studio.models.GCodeProgram`.

Output is an EDUCATIONAL starting point. It is NOT a certified post-processor and
is NOT guaranteed safe to run. Always verify before use.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..models import GCodeProgram
from .body import body_lines_from_moves, build_etch_body, build_manual_body
from .dialects import get_dialect
from .footer import build_footer, footer_from_config, footer_lines
from .formatter import render
from .header import build_header, header_from_config, header_lines

__all__ = [
    "build_header",
    "build_manual_body",
    "build_etch_body",
    "build_footer",
    "build_program",
    "program_to_text",
    "program_from_config",
]


def build_program(config: Mapping[str, Any], job: Mapping[str, Any]) -> str:
    """Assemble a complete program from a config + a job (dict adapter).

    job = {"mode": "manual", "moves": [...]}
    job = {"mode": "etch",   "paths": [...]}   (etch settings on config['etch'])
    """
    if job.get("mode") == "etch":
        body = build_etch_body(job.get("paths", []), config)
    else:
        body = build_manual_body(job.get("moves", []), config)

    return "\n".join([*build_header(config), "", *body, "", *build_footer(config)])


def program_to_text(program: GCodeProgram) -> str:
    """Render a typed :class:`GCodeProgram` to G-code text (object path)."""
    is_marlin = get_dialect(program.header.machine).id == "marlin"
    header = [render(ln) for ln in header_lines(program.header)]
    body = [render(ln) for ln in body_lines_from_moves(program.moves, is_marlin)]
    footer = [render(ln) for ln in footer_lines(program.footer)]
    return "\n".join([*header, "", *body, "", *footer])


def program_from_config(config: Mapping[str, Any], moves) -> GCodeProgram:
    """Build a typed :class:`GCodeProgram` from a legacy config + typed moves."""
    return GCodeProgram(
        header=header_from_config(config),
        moves=list(moves),
        footer=footer_from_config(config),
    )
