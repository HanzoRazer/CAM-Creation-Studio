"""CLI subcommands.

Each module exposes ``add_parser(subparsers)`` which registers the command and
wires ``set_defaults(func=run)``; ``run(args) -> int`` performs the work and
returns an exit code. ``main`` discovers commands through :data:`COMMANDS`.
"""

from . import feeds, generate, parse, preview, validate, version

COMMANDS = (generate, validate, parse, preview, feeds, version)

__all__ = ["COMMANDS"]
