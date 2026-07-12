"""``camstudio preview`` — a textual toolpath summary (no rendering).

Builds the neutral toolpath model (``preview.build_toolpath_model``) and reports
segment counts and travelled distance per motion type. This is a summary only:
the CLI never rasterizes or draws anything.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List

from ...preview.toolpath_model import build_toolpath_model
from ..common import add_input_arg, add_json_flag, read_text
from ..errors import EXIT_OK
from ..output import format_table, render


def summarize_segments(segs: List[Any]) -> Dict[str, Any]:
    """Per-type counts and distances plus totals for a list of ToolpathSegments."""
    by_type: Dict[str, Dict[str, float]] = {}
    for s in segs:
        bucket = by_type.setdefault(s.type, {"count": 0, "distance": 0.0})
        bucket["count"] += 1
        bucket["distance"] += s.distance or 0.0
    total_distance = round(sum(b["distance"] for b in by_type.values()), 3)
    for b in by_type.values():
        b["distance"] = round(b["distance"], 3)
    return {
        "segments": len(segs),
        "total_distance": total_distance,
        "by_type": by_type,
    }


def _human(summary: Dict[str, Any]) -> str:
    rows = [
        (t, v["count"], v["distance"])
        for t, v in sorted(summary["by_type"].items())
    ]
    table = format_table(["type", "count", "distance(mm)"], rows) if rows else "(no motion)"
    return (
        f"{summary['segments']} segment(s), "
        f"total travel {summary['total_distance']} mm\n\n{table}"
    )


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "preview",
        help="summarize a toolpath (counts and distances; no rendering)",
        description="Toolpath summary of a G-code program (file or stdin).",
    )
    add_input_arg(p, "G-code to summarize")
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    text = read_text(args.input)
    summary = summarize_segments(build_toolpath_model(text))
    render(json_mode=args.json, human_text=_human(summary), json_obj=summary)
    return EXIT_OK
