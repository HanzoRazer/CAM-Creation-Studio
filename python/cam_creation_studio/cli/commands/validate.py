"""``camstudio validate`` — advisory validation of a G-code program.

Runs ``gcode.validator.validate_program`` and reports diagnostics. Validation is
advisory and never rewrites a program; here the CLI simply signals the result
through an exit code: ``1`` when any warning/danger diagnostic is present, ``0``
when the program is clean (info-only). This owns no validation rules.
"""

from __future__ import annotations

import argparse

from ...enums import DiagnosticSeverity
from ...gcode.validator import validate_program
from ..common import add_input_arg, add_json_flag, read_text
from ..errors import EXIT_OK, EXIT_VALIDATION
from ..output import render

_FAIL_SEVERITIES = {DiagnosticSeverity.WARNING, DiagnosticSeverity.DANGER}


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "validate",
        help="run advisory validation and report diagnostics",
        description="Advisory validation of a G-code program (file or stdin).",
    )
    add_input_arg(p, "G-code to validate")
    p.add_argument(
        "-m", "--machine", default=None,
        help="machine dialect for cross-dialect checks (e.g. genericCnc, marlin, laserGrbl)",
    )
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    text = read_text(args.input)
    diags = validate_program(text, args.machine)

    failed = any(d.severity in _FAIL_SEVERITIES for d in diags)

    if diags:
        lines = [
            f"{d.severity.value.upper():7} [{d.code}]"
            + (f" line {d.line}" if d.line is not None else "")
            + f": {d.message}"
            for d in diags
        ]
        human = "\n".join(lines) + f"\n\n{len(diags)} diagnostic(s); "
        human += "FAIL" if failed else "OK (info only)"
    else:
        human = "OK — no diagnostics."

    render(
        json_mode=args.json,
        human_text=human,
        json_obj={
            "ok": not failed,
            "diagnostics": [d.as_dict() for d in diags],
            "count": len(diags),
        },
    )
    return EXIT_VALIDATION if failed else EXIT_OK
