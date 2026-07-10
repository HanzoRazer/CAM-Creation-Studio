"""Exit codes and the exception → code mapping for the CLI.

Standard, stable exit codes so the CLI is scriptable and CI-friendly:

    0  success
    1  validation failure (a command found problems in otherwise valid input)
    2  bad arguments / bad input (unusable flags, malformed JSON payload)
    3  file error (missing / unreadable / unwritable path)

Commands raise the :class:`CliError` subclasses below; :func:`exit_code_for`
also maps the builtin exceptions the core can raise so a command never has to
wrap every OS call.
"""

from __future__ import annotations

import json

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_FILE = 3


class CliError(Exception):
    """A user-facing CLI error carrying the process exit code to return."""

    exit_code = EXIT_VALIDATION


class ValidationFailure(CliError):
    """Input was processed but found wanting (e.g. validation diagnostics)."""

    exit_code = EXIT_VALIDATION


class UsageError(CliError):
    """Unusable arguments or malformed input (bad flags, invalid JSON)."""

    exit_code = EXIT_USAGE


class FileError(CliError):
    """A file could not be read or written."""

    exit_code = EXIT_FILE


def exit_code_for(exc: BaseException) -> int:
    """Best-effort exit code for an exception escaping a command."""
    if isinstance(exc, CliError):
        return exc.exit_code
    if isinstance(exc, (FileNotFoundError, IsADirectoryError, PermissionError)):
        return EXIT_FILE
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return EXIT_USAGE
    return EXIT_VALIDATION
