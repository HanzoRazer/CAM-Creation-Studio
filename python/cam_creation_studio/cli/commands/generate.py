"""``camstudio generate`` — build G-code from a job description.

Input is a ``{"config": {...}, "job": {...}}`` JSON document (the same shape as
``examples/*.json``), read from a file or stdin. A few convenience flags override
fields of ``config`` without editing the file. The heavy lifting is entirely
``gcode.generator.build_program`` — this command only reads, overrides, runs
export preflight, and writes.

This is the export boundary. Generation itself never blocks; but before an
artifact reaches stdout or a file, ``safety.preflight.run_export_preflight``
decides whether policy permits it. Blocking findings stop the write and exit
non-zero — no file is created, and an existing file is left untouched. Advisory
findings are printed to stderr and the export proceeds. No policy logic lives
here: this module only calls the canonical gate and reports what it says.
"""

from __future__ import annotations

import argparse
import sys

from ...gcode.generator import build_program
from ...safety.preflight import run_export_preflight
from ..common import add_json_flag, read_json, write_text
from ..errors import EXIT_OK, EXIT_VALIDATION, UsageError
from ..output import dump_json


def _finding_lines(diagnostics) -> list:
    """Render diagnostics the way ``camstudio validate`` does, for consistency."""
    return [
        f"{d.severity.value.upper():7} [{d.code}]"
        + (f" line {d.line}" if d.line is not None else "")
        + f": {d.message}"
        for d in diagnostics
    ]


def _report(result) -> None:
    """Print the preflight outcome to stderr, blocking findings first.

    stderr keeps stdout clean for the G-code itself, so ``camstudio generate job
    .json > part.gcode`` stays usable while the operator still sees the report.
    """
    print(result.summary(), file=sys.stderr)
    if result.blocking_findings:
        print("\nBlocking:", file=sys.stderr)
        for line in _finding_lines(result.blocking_findings):
            print(f"  {line}", file=sys.stderr)
    if result.advisory_findings:
        print("\nAdvisory:", file=sys.stderr)
        for line in _finding_lines(result.advisory_findings):
            print(f"  {line}", file=sys.stderr)
    if not result.export_allowed:
        print("\nNo G-code was written.", file=sys.stderr)
    print(f"\n{result.disclaimer}", file=sys.stderr)

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

    # The export boundary. Everything above produced a candidate artifact;
    # nothing below writes one unless policy allows it.
    result = run_export_preflight(gcode, config)
    _report(result)

    if not result.export_allowed:
        # Diagnostics stay available when export does not: --json still yields a
        # machine-readable report on stdout. It deliberately carries no "gcode"
        # key, so nothing downstream can mistake it for an approved artifact,
        # and it never goes to --output.
        if args.json:
            print(dump_json({"preflight": result.as_dict()}))
        return EXIT_VALIDATION

    if args.json and args.output:
        # The file will hold a JSON envelope, not raw G-code — easy to miss when
        # the path looks like a finished program (e.g. -o part.gcode). Say so on
        # stderr; stdout/exit code are unaffected so scripts that mean it are fine.
        print(
            f"note: --json writes a JSON envelope to {args.output}, not raw "
            "G-code; drop --json for a runnable program.",
            file=sys.stderr,
        )

    payload = (
        dump_json({"gcode": gcode, "preflight": result.as_dict()})
        if args.json else gcode
    )
    write_text(payload, args.output)
    return EXIT_OK
