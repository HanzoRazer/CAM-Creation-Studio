"""Non-blocking G-code validation.

Emits advisory diagnostics about a program — it never blocks generation. Rules
are split by concern into four modules, each returning
:class:`~cam_creation_studio.models.Diagnostic` objects:

* :mod:`structure`    — is the program well-formed (units, body, safe Z, end)?
* :mod:`dialect`      — does it fit the named machine's dialect?
* :mod:`crossdialect` — is a command in the wrong machine family?
* :mod:`safety`       — could it do something dangerous (no feed, spindle off, ...)?

:func:`validate_program` runs them all and merges their findings. Diagnostics
are hints to help a beginner catch common mistakes; they are not a safety
guarantee. Every code is defined in :mod:`codes`; use
:func:`~cam_creation_studio.gcode.validator.codes.has_code` to check for one
(it resolves legacy aliases).
"""

from __future__ import annotations

from typing import List, Optional

from ...enums import DiagnosticSeverity
from ...models import Diagnostic
from . import codes, crossdialect, dialect, safety, structure
from ._context import ProgramContext, build_context
from .codes import CANONICAL_CODES, canonical_code, has_code

# Back-compat aliases: this module exposed ``Warning`` and string severity
# constants before CS-002. They now point at the typed Diagnostic model.
Warning = Diagnostic
INFO = DiagnosticSeverity.INFO
WARNING = DiagnosticSeverity.WARNING
DANGER = DiagnosticSeverity.DANGER

__all__ = [
    "validate_program",
    "Diagnostic",
    "Warning",
    "DiagnosticSeverity",
    "ProgramContext",
    "build_context",
    "codes",
    "CANONICAL_CODES",
    "canonical_code",
    "has_code",
    "INFO",
    "WARNING",
    "DANGER",
]


def validate_program(text: str, machine: Optional[str] = None) -> List[Diagnostic]:
    """Validate a G-code program string. Returns advisory Diagnostics.

    Order: structural findings first, then dialect conformance, then
    cross-dialect contamination, then safety.
    """
    ctx = build_context(text, machine)
    diagnostics: List[Diagnostic] = []
    diagnostics.extend(structure.check(ctx))
    diagnostics.extend(dialect.check(ctx))
    diagnostics.extend(crossdialect.check(ctx))
    diagnostics.extend(safety.check(ctx))
    return diagnostics
