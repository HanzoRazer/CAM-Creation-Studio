"""Shared argparse helpers and I/O for CLI commands.

Centralizes the flags and file handling every command needs so the command
modules stay focused on calling the core and shaping output.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .errors import FileError, UsageError


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add the standard ``--json`` switch (human output remains the default)."""
    parser.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable text",
    )


def add_input_arg(parser: argparse.ArgumentParser, help_text: str) -> None:
    """Add an optional input path positional; '-' or omitted means stdin."""
    parser.add_argument(
        "input", nargs="?", default="-",
        help=f"{help_text} (path, or '-'/omitted for stdin)",
    )


def read_text(path: str) -> str:
    """Read text from ``path``, or stdin when ``path`` is '-' or empty."""
    if path in ("-", "", None):
        return sys.stdin.read()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
        raise FileError(f"cannot read {path}: {exc.strerror or exc}") from exc


def read_json(path: str) -> Any:
    """Read and parse JSON from ``path`` or stdin; malformed JSON is a usage error."""
    raw = read_text(path)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        where = "stdin" if path in ("-", "", None) else path
        raise UsageError(f"invalid JSON in {where}: {exc}") from exc


def write_text(text: str, path: str | None) -> None:
    """Write ``text`` to ``path``, or stdout when ``path`` is None."""
    if not path:
        print(text)
        return
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
    except (IsADirectoryError, PermissionError, FileNotFoundError) as exc:
        raise FileError(f"cannot write {path}: {exc.strerror or exc}") from exc
