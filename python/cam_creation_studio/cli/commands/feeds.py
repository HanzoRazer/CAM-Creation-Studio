"""``camstudio feeds`` — advisory feeds & speeds recommendation.

Maps flags onto ``feeds_speeds.calculator.calculate_feeds`` and prints the
resulting :class:`FeedRecommendation`. Every number is ADVISORY — a starting
point requiring operator verification, never a certified value. The calculator
owns all the math; this command only gathers inputs and formats the result.
"""

from __future__ import annotations

import argparse

from ...feeds_speeds.calculator import calculate_feeds
from ..common import add_json_flag
from ..errors import EXIT_OK, UsageError
from ..output import kv_block, render


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "feeds",
        help="compute an advisory feeds & speeds recommendation",
        description="Advisory feeds & speeds (a starting point; verify before cutting).",
    )
    p.add_argument("-d", "--tool-diameter", type=float, required=True,
                   help="tool diameter in mm")
    p.add_argument("-n", "--flutes", type=int, required=True,
                   help="number of flutes/teeth")
    p.add_argument("-r", "--rpm", type=float, required=True,
                   help="spindle speed in RPM")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--material", default=None,
                     help="material id for a conservative chipload (e.g. aluminum, hardwood)")
    src.add_argument("--chipload", type=float, default=None,
                     help="explicit chipload in mm/tooth")
    p.add_argument("--woc", type=float, default=None, help="width of cut in mm")
    p.add_argument("--doc", type=float, default=None, help="depth of cut in mm")
    p.add_argument("--max-rpm", type=float, default=None,
                   help="machine RPM ceiling (adds a warning if exceeded)")
    p.add_argument("--feed-override", type=float, default=None,
                   help="use this feed (mm/min) instead of the computed value")
    add_json_flag(p)
    p.set_defaults(func=run)


def _human(rec) -> str:
    d = rec.as_dict()
    core = kv_block([
        ("rpm", f"{d['rpm']:g}"),
        ("feed rate", f"{d['feed_rate']:g} mm/min"),
        ("chipload", f"{d['chipload']:g} mm/tooth"),
        ("surface speed", f"{d['surface_speed']:g} mm/min"),
        ("chip thinning", f"{d['chip_thinning_factor']:g}x"),
        ("MRR", None if d["material_removal_rate"] is None
                else f"{d['material_removal_rate']:g} mm^3/min"),
        ("spindle power", None if d["spindle_power_kw"] is None
                          else f"{d['spindle_power_kw']:g} kW"),
    ], title="Recommendation (ADVISORY)")
    parts = [core]
    if rec.warnings:
        parts.append("Warnings\n" + "\n".join(f"  - {w}" for w in rec.warnings))
    return "\n\n".join(parts)


def run(args: argparse.Namespace) -> int:
    try:
        rec = calculate_feeds(
            tool_diameter_mm=args.tool_diameter,
            flutes=args.flutes,
            spindle_rpm=args.rpm,
            material=args.material,
            chipload=args.chipload,
            woc_mm=args.woc,
            doc_mm=args.doc,
            max_rpm=args.max_rpm,
            feed_override=args.feed_override,
        )
    except ValueError as exc:
        raise UsageError(str(exc)) from exc

    render(json_mode=args.json, human_text=_human(rec), json_obj=rec.as_dict())
    return EXIT_OK
