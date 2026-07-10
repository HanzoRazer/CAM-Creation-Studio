"""CLI entry point: argument parsing and command dispatch.

``main`` builds the top-level parser, lets each command register its subparser,
runs the selected command, and maps any escaping exception to a standard exit
code. It contains no business logic — dispatch only.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .commands import COMMANDS
from .commands.version import get_version
from .errors import EXIT_USAGE, exit_code_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="camstudio",
        description=(
            "CAM-Creation-Studio CLI — generate, parse, validate, and inspect "
            "G-code, and compute advisory feeds/speeds. Educational: verify all "
            "output before running on real hardware."
        ),
    )
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"camstudio {get_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True
    for command in COMMANDS:
        command.add_parser(subparsers)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("interrupted", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - top-level boundary maps to exit code
        print(f"error: {exc}", file=sys.stderr)
        return exit_code_for(exc)


if __name__ == "__main__":
    raise SystemExit(main())
