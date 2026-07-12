"""Exit codes and the exception → code mapping for the CLI.

Standard, stable exit codes so the CLI is scriptable and CI-friendly:

    0   success
    1   validation failure (a command found problems in otherwise valid input)
    2   bad arguments / bad input (unusable flags, malformed JSON payload)
    3   file error (missing / unreadable / unwritable path)
    70  internal error (an unexpected exception escaped a command — a bug)

Commands raise the :class:`CliError` subclasses below; :func:`exit_code_for`
also maps the builtin exceptions the core can raise so a command never has to
wrap every OS call. Anything a command does *not* anticipate is treated as an
internal defect (code 70) rather than being disguised as user error, so a crash
is never confused with bad input (2) or a genuine validation finding (1).
"""

from __future__ import annotations

import json

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_FILE = 3
EXIT_INTERNAL = 70  # EX_SOFTWARE (sysexits.h): an internal software error


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
    """Best-effort exit code for an exception escaping a command.

    Only exceptions that unambiguously mean "the user's input/environment was
    at fault" map to user-facing codes (file 3, usage 2). Commands that expect a
    ``ValueError`` from the core already wrap it in a :class:`UsageError`
    themselves, so any *unwrapped* exception reaching here — including a bare
    ``ValueError`` — is an unexpected defect and maps to ``EXIT_INTERNAL``.
    """
    if isinstance(exc, CliError):
        return exc.exit_code
    if isinstance(exc, (FileNotFoundError, IsADirectoryError, PermissionError)):
        return EXIT_FILE
    # JSONDecodeError subclasses ValueError; check it first — malformed JSON is
    # genuinely bad input, but a plain ValueError is not assumed to be.
    if isinstance(exc, json.JSONDecodeError):
        return EXIT_USAGE
    return EXIT_INTERNAL
