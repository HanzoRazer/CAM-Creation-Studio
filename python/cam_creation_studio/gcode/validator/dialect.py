"""Dialect-conformance rules — does the program fit the target machine?

  UNSUPPORTED_DIALECT       the named machine/dialect is not recognized
  ARC_ON_NON_ARC_DIALECT    G2/G3 used on a dialect that does not do arcs

When no machine is named there is nothing dialect-specific to check, so these
rules stay silent — the generic structure/safety rules still apply.
"""

from __future__ import annotations

from typing import List

from ...enums import DiagnosticSeverity
from ...models import Diagnostic
from ..dialects import get_dialect
from ._context import ProgramContext


def check(ctx: ProgramContext) -> List[Diagnostic]:
    if ctx.machine is None:
        return []

    try:
        dialect = get_dialect(ctx.machine)
    except ValueError:
        return [Diagnostic(
            DiagnosticSeverity.WARNING, "UNSUPPORTED_DIALECT",
            f"Unrecognized machine/dialect '{ctx.machine}'.")]

    diagnostics: List[Diagnostic] = []
    if not dialect.supports_arcs:
        for ln in ctx.lines:
            if ln.is_arc:
                diagnostics.append(Diagnostic(
                    DiagnosticSeverity.WARNING, "ARC_ON_NON_ARC_DIALECT",
                    f"Arc move (G2/G3) on '{dialect.label}', which does not "
                    "support arcs.", ln.number))
    return diagnostics
