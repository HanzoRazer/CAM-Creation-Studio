"""``camstudio validate`` — advisory validation of a G-code program.

Runs ``gcode.validator.validate_program`` and reports diagnostics. Validation is
advisory and never rewrites a program; here the CLI simply signals the result
through an exit code. By default (``--fail-on warning``) exit ``1`` when any
warning/danger diagnostic is present and ``0`` otherwise, but ``--fail-on``
lets a script relax that to ``danger`` (fail only on danger) or ``never`` (always
exit ``0`` and just report). This owns no validation rules.
"""

from __future__ import annotations

import argparse

from ...enums import DiagnosticSeverity
from ...gcode.validator import validate_program
from ..common import add_input_arg, add_json_flag, read_text
from ..errors import EXIT_OK, EXIT_VALIDATION
from ..output import render

# Severities that count as a failure for each --fail-on policy.
_FAIL_POLICIES = {
    "never": frozenset(),
    "danger": frozenset({DiagnosticSeverity.DANGER}),
    "warning": frozenset({DiagnosticSeverity.WARNING, DiagnosticSeverity.DANGER}),
}
_DEFAULT_FAIL_ON = "warning"


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
    p.add_argument(
        "--fail-on", choices=sorted(_FAIL_POLICIES), default=_DEFAULT_FAIL_ON,
        help="lowest severity that makes the exit code non-zero "
             "(default: warning; use 'danger' to ignore warnings, "
             "'never' to always exit 0)",
    )
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    text = read_text(args.input)
    diags = validate_program(text, args.machine)

    fail_severities = _FAIL_POLICIES[args.fail_on]
    failed = any(d.severity in fail_severities for d in diags)

    if diags:
        lines = [
            f"{d.severity.value.upper():7} [{d.code}]"
            + (f" line {d.line}" if d.line is not None else "")
            + f": {d.message}"
            for d in diags
        ]
        if failed:
            verdict = "FAIL"
        elif fail_severities:
            # Nothing at/above the threshold, but lesser diagnostics remain.
            verdict = "OK (below --fail-on threshold)"
        else:
            verdict = "OK (--fail-on never)"
        human = "\n".join(lines) + f"\n\n{len(diags)} diagnostic(s); {verdict}"
    else:
        human = "OK — no diagnostics."

    render(
        json_mode=args.json,
        human_text=human,
        json_obj={
            "ok": not failed,
            "fail_on": args.fail_on,
            "diagnostics": [d.as_dict() for d in diags],
            "count": len(diags),
        },
    )
    return EXIT_VALIDATION if failed else EXIT_OK
