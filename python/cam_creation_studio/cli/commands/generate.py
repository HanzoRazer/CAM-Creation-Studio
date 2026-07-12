"""``camstudio generate`` — build G-code from a job description.

Input is a ``{"config": {...}, "job": {...}}`` JSON document (the same shape as
``examples/*.json``), read from a file or stdin. A few convenience flags override
fields of ``config`` without editing the file. The heavy lifting is entirely
``gcode.generator.build_program`` — this command only reads, overrides, and
writes.
"""

from __future__ import annotations

import argparse
import sys

from ...gcode.generator import build_program
from ..common import add_json_flag, read_json, write_text
from ..errors import EXIT_OK, UsageError
from ..output import dump_json

_OVERRIDES = (
    ("machine", "--machine", "override config.machine (e.g. genericCnc, marlin, laser)"),
    ("units", "--units", "override config.units (mm or in)"),
    ("safeZ", "--safe-z", "override config.safeZ retract height", float),
)


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "generate",
        help="build G-code from a {config, job} JSON document",
        description="Build G-code from a {config, job} JSON job (file or stdin).",
    )
    p.add_argument(
        "input", nargs="?", default="-",
        help="job JSON path, or '-'/omitted for stdin",
    )
    p.add_argument(
        "-o", "--output", default=None,
        help="write G-code to this file instead of stdout",
    )
    for name, flag, help_text, *rest in _OVERRIDES:
        p.add_argument(flag, dest=name, default=None,
                       type=(rest[0] if rest else str), help=help_text)
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    doc = read_json(args.input)
    if not isinstance(doc, dict) or "job" not in doc:
        raise UsageError(
            "generate expects a JSON object with a 'job' key "
            "(and usually a 'config'); see examples/*.json")

    config = dict(doc.get("config") or {})
    job = doc["job"]

    for name, flag, *_ in _OVERRIDES:
        value = getattr(args, name, None)
        if value is not None:
            config[name] = value

    try:
        gcode = build_program(config, job)
    except (KeyError, TypeError, ValueError) as exc:
        raise UsageError(f"could not generate G-code: {exc}") from exc

    if args.json and args.output:
        # The file will hold a JSON envelope, not raw G-code — easy to miss when
        # the path looks machine-ready (e.g. -o part.gcode). Say so on stderr;
        # stdout/exit code are unaffected so scripts that mean it are fine.
        print(
            f"note: --json writes a JSON envelope to {args.output}, not raw "
            "G-code; drop --json for a runnable program.",
            file=sys.stderr,
        )

    payload = dump_json({"gcode": gcode}) if args.json else gcode
    write_text(payload, args.output)
    return EXIT_OK
