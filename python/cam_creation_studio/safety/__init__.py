"""Safety messaging and the export-preflight policy gate.

Two responsibilities, deliberately separate:

* :mod:`rules` — the standing advisory reminders and the canonical ``DISCLAIMER``.
  Advisory only; nothing here blocks anything.
* :mod:`preflight` — the one policy gate that decides whether a generated
  artifact may be written. It blocks only what Creation Studio can *know* is
  wrong (contradictions, unrepresentable output); anything requiring knowledge of
  a real machine stays advisory.

Neither certifies machine readiness. See
``docs/architecture/EXPORT_PREFLIGHT_SEMANTICS.md``.
"""

from .preflight import (  # noqa: F401
    POLICY_VERSION,
    ExportPreflightResult,
    run_export_preflight,
)
from .rules import DISCLAIMER, SafetyRule, all_rules, checklist, get_rule  # noqa: F401

__all__ = [
    "DISCLAIMER",
    "SafetyRule",
    "all_rules",
    "get_rule",
    "checklist",
    "POLICY_VERSION",
    "ExportPreflightResult",
    "run_export_preflight",
]
