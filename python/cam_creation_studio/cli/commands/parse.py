"""``camstudio parse`` — parse a program and report statistics.

Lifts text into the typed model (``parser.parse_program_model``) and reports move
counts by command, the inferred header facts, the program bounds, and travelled
distance (via the toolpath model). No business logic lives here.
"""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any, Dict, Optional

from ...gcode.parser import parse_program_model
from ...preview.toolpath_model import build_toolpath_model
from ..common import add_input_arg, add_json_flag, read_text
from ..errors import EXIT_OK
from ..output import kv_block, render
from .preview import summarize_segments


def _bounds_dict(bounds) -> Optional[Dict[str, float]]:
    if bounds is None:
        return None
    # Round every coordinate (not just the spans) so the JSON contract has a
    # single, stable precision and float noise never leaks into output.
    r = lambda v: round(v, 3)
    return {
        "min_x": r(bounds.min_x), "min_y": r(bounds.min_y),
        "max_x": r(bounds.max_x), "max_y": r(bounds.max_y),
        "min_z": r(bounds.min_z), "max_z": r(bounds.max_z),
        "width": r(bounds.width), "height": r(bounds.height),
        "depth": r(bounds.depth),
    }


def _stats(text: str) -> Dict[str, Any]:
    prog = parse_program_model(text)
    counts = Counter(m.type.value for m in prog.moves)
    toolpath = summarize_segments(build_toolpath_model(text))
    return {
        "moves": len(prog.moves),
        "moves_by_command": dict(sorted(counts.items())),
        "header": {
            "units": prog.header.units.value,
            "absolute": prog.header.absolute,
            "machine": prog.header.machine,
        },
        "bounds": _bounds_dict(prog.bounds()),
        "toolpath": toolpath,
    }


def _human(stats: Dict[str, Any]) -> str:
    cmds = ", ".join(f"{k}={v}" for k, v in stats["moves_by_command"].items()) or "(none)"
    blocks = [
        kv_block([
            ("moves", stats["moves"]),
            ("by command", cmds),
            ("units", stats["header"]["units"]),
            ("machine", stats["header"]["machine"]),
            ("total travel", f"{stats['toolpath']['total_distance']} mm"),
        ], title="Program"),
    ]
    b = stats["bounds"]
    if b:
        blocks.append(kv_block([
            ("x", f"{b['min_x']} .. {b['max_x']}  (w {b['width']})"),
            ("y", f"{b['min_y']} .. {b['max_y']}  (h {b['height']})"),
            ("z", f"{b['min_z']} .. {b['max_z']}  (d {b['depth']})"),
        ], title="Bounds"))
    else:
        blocks.append("Bounds\n  (no positioned moves)")
    return "\n\n".join(blocks)


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "parse",
        help="parse a program and report statistics, bounds, and distances",
        description="Parse a G-code program (file or stdin) and report statistics.",
    )
    add_input_arg(p, "G-code to parse")
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    stats = _stats(read_text(args.input))
    render(json_mode=args.json, human_text=_human(stats), json_obj=stats)
    return EXIT_OK
