"""``camstudio version`` — report the installed package version.

The same string backs the top-level ``camstudio --version`` flag.
"""

from __future__ import annotations

import argparse

from ..errors import EXIT_OK
from ..output import render

_DISTRIBUTION = "cam-creation-studio"
_FALLBACK = "0.1.0"


def get_version() -> str:
    """Installed distribution version, or a fallback for source checkouts."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version(_DISTRIBUTION)
        except PackageNotFoundError:
            return _FALLBACK
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib >=3.8
        return _FALLBACK


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "version",
        help="print the camstudio version",
        description="Print the installed camstudio version.",
    )
    from ..common import add_json_flag
    add_json_flag(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    v = get_version()
    render(
        json_mode=getattr(args, "json", False),
        human_text=f"camstudio {v}",
        json_obj={"name": "camstudio", "version": v},
    )
    return EXIT_OK
