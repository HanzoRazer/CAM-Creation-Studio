"""Export preflight — the one policy gate between a generated program and a file.

Creation Studio generates freely and validates advisorily: ``validate_program``
never blocks anything. That is the right posture for authoring and learning, but
it means nothing stands between a malformed program and a ``.gcode`` file on
disk. This module is that gate, and only that gate.

    run_export_preflight(gcode, config) -> ExportPreflightResult

Preflight is a *policy layer*, not a new subsystem. It does not parse G-code
(:mod:`~cam_creation_studio.gcode.parser` does), does not detect program
problems (:mod:`~cam_creation_studio.gcode.validator` does), and does not define
diagnostics (:class:`~cam_creation_studio.models.Diagnostic` does). It runs the
existing validator, sorts what comes back into *blocking* and *advisory* by an
explicit policy table, adds the few checks that only matter at the export
boundary, and returns an immutable result.

What preflight blocks, and what it only reports
-----------------------------------------------
The line is drawn on **what Creation Studio can actually know**:

* **Blocking** — the program is internally contradictory or cannot be
  represented for the selected dialect. Conflicting units, an arc with no center
  or radius, an arc on a dialect without arc support, a non-finite coordinate, a
  non-positive feed on a feed move. These are wrong on their face; no knowledge
  of the shop changes that.

* **Advisory** — everything whose truth depends on the machine, the stock, the
  tooling, or the operator. Spindle never started, no safe-Z retract, cutting
  move with no feed in effect. These may be real hazards or entirely fine, and
  Creation Studio cannot tell which.

Blocking on the second group would be an implicit claim to machine authority,
which ``docs/product-scope.md`` forbids. Advisory findings therefore stay
advisory no matter how alarming they sound — they are surfaced loudly and the
operator decides.

A passing preflight means only: *Creation Studio found no condition in its
current policy that blocks export.* It is not a claim that the program is safe
to run, machine-ready, or certified. See
``docs/architecture/EXPORT_PREFLIGHT_SEMANTICS.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Tuple

from ..enums import DiagnosticSeverity, Units
from ..gcode.parser import parse_program
from ..gcode.validator import codes, validate_program
from ..models import Diagnostic
from .rules import DISCLAIMER

__all__ = [
    "POLICY_VERSION",
    "BLOCKING_CODES",
    "ExportPreflightResult",
    "run_export_preflight",
]

# Bump when a blocking classification changes, a blocking rule is added or
# removed, or the meaning of export eligibility changes. Wording-only edits to
# messages or documentation do not require a bump.
POLICY_VERSION = "cs-export-preflight/1"


# --------------------------------------------------------------------------- #
# Policy: which existing validator codes block export
# --------------------------------------------------------------------------- #
# Only codes describing an internal contradiction or an unrepresentable program
# appear here. Severity alone does not decide it: SPINDLE_OFF_WITH_CUTS is
# DANGER and stays advisory, because whether it is true depends on a machine
# Creation Studio cannot see; DUPLICATE_UNITS is DANGER and blocks, because a
# program declaring both G20 and G21 is wrong on its own terms.
BLOCKING_CODES = frozenset({
    codes.DUPLICATE_UNITS,                  # contradictory unit declarations
    codes.ARC_WITHOUT_CENTER_OR_RADIUS,     # arc geometry is unresolvable
    codes.ARC_ON_NON_ARC_DIALECT,           # cannot be represented for the target
    codes.UNSUPPORTED_DIALECT,              # target dialect is not known
    # Export-boundary checks this module raises itself.
    codes.EXPORT_EMPTY_ARTIFACT,
    codes.EXPORT_NON_FINITE_VALUE,
    codes.EXPORT_UNIT_MISMATCH,
    codes.EXPORT_NON_POSITIVE_FEED,
})

# Stable identifiers for the checks preflight itself performs, so a result can
# say what ran and what did not.
RULE_EMPTY_ARTIFACT = "preflight.empty_artifact"
RULE_REUSED_VALIDATOR = "preflight.validator_findings"
RULE_UNIT_AGREEMENT = "preflight.unit_agreement"
RULE_NON_FINITE = "preflight.non_finite_values"
RULE_FEED_POSITIVE = "preflight.positive_feed"

# Policy rule order — also the order checks run in, so results stay comparable.
ALL_RULE_IDS = (
    RULE_EMPTY_ARTIFACT,
    RULE_REUSED_VALIDATOR,
    RULE_UNIT_AGREEMENT,
    RULE_NON_FINITE,
    RULE_FEED_POSITIVE,
)

# ``nan``/``inf`` never survive this project's formatter (``round_for_gcode``
# raises on them), but text can reach preflight from a file, an editor, or
# another tool. Matched as a whole token directly after an axis/parameter letter
# — and only in the code part of a line, never in a comment.
_NON_FINITE_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z])\s*([+-]?(?:nan|inf(?:inity)?))(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_COMMENT_SEMI_RE = re.compile(r";.*$")
_COMMENT_PAREN_RE = re.compile(r"\([^)]*\)")


def _code_part(raw: str) -> str:
    """The executable part of a line, with ';' and '(...)' comments removed."""
    return _COMMENT_SEMI_RE.sub("", _COMMENT_PAREN_RE.sub(" ", raw))


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ExportPreflightResult:
    """The outcome of one preflight evaluation. Immutable and deterministic.

    ``export_allowed`` is ``True`` exactly when ``blocking_findings`` is empty.
    Advisory findings never affect it — they are reported so the operator can
    weigh them, which is the only place that judgement can correctly live.

    Carries no timestamp on purpose: equal inputs must produce equal results, so
    fixtures stay stable and repeated evaluation is verifiably identical.
    """

    export_allowed: bool
    blocking_findings: Tuple[Diagnostic, ...] = ()
    advisory_findings: Tuple[Diagnostic, ...] = ()
    policy_version: str = POLICY_VERSION
    disclaimer: str = DISCLAIMER
    evaluated_rule_ids: Tuple[str, ...] = ()
    skipped_rule_ids: Tuple[str, ...] = ()

    @property
    def findings(self) -> Tuple[Diagnostic, ...]:
        """All findings, blocking first — the display order."""
        return self.blocking_findings + self.advisory_findings

    def summary(self) -> str:
        """One line stating the outcome, in permitted vocabulary."""
        verdict = (
            "Export preflight passed." if self.export_allowed
            else "Export blocked by preflight."
        )
        return (
            f"{verdict} {len(self.blocking_findings)} blocking finding(s), "
            f"{len(self.advisory_findings)} advisory."
        )

    def as_dict(self) -> dict:
        """Plain-data form, following :meth:`Diagnostic.as_dict` conventions."""
        return {
            "export_allowed": self.export_allowed,
            "blocking_findings": [d.as_dict() for d in self.blocking_findings],
            "advisory_findings": [d.as_dict() for d in self.advisory_findings],
            "policy_version": self.policy_version,
            "disclaimer": self.disclaimer,
            "evaluated_rule_ids": list(self.evaluated_rule_ids),
            "skipped_rule_ids": list(self.skipped_rule_ids),
        }


# --------------------------------------------------------------------------- #
# Deterministic ordering
# --------------------------------------------------------------------------- #
_SEVERITY_RANK = {
    DiagnosticSeverity.DANGER: 0,
    DiagnosticSeverity.WARNING: 1,
    DiagnosticSeverity.INFO: 2,
}


def _sort_key(diag: Diagnostic) -> tuple:
    """Order by program location, then severity, then code, then message.

    Line ``None`` sorts before any numbered line: a program-wide finding is not
    attached to a location and reads first. Nothing here consults a dict, a set,
    or the filesystem, so the order cannot drift between runs.
    """
    return (
        0 if diag.line is None else 1,
        diag.line if diag.line is not None else 0,
        _SEVERITY_RANK.get(diag.severity, 99),
        diag.code,
        diag.message,
    )


# --------------------------------------------------------------------------- #
# Export-boundary checks
# --------------------------------------------------------------------------- #
def _check_empty(gcode: str) -> List[Diagnostic]:
    """An artifact with no content at all is not exportable."""
    if gcode.strip():
        return []
    return [Diagnostic(
        DiagnosticSeverity.DANGER, codes.EXPORT_EMPTY_ARTIFACT,
        "Nothing to export — the generated program is empty.")]


def _check_non_finite(gcode: str) -> List[Diagnostic]:
    """Reject NaN/Inf parameter values, which no controller can honor."""
    found: List[Diagnostic] = []
    for number, raw in enumerate(gcode.splitlines(), start=1):
        for letter, token in _NON_FINITE_RE.findall(_code_part(raw)):
            found.append(Diagnostic(
                DiagnosticSeverity.DANGER, codes.EXPORT_NON_FINITE_VALUE,
                f"Non-finite value '{letter.upper()}{token}' — coordinates and "
                "parameters must be finite numbers.", number))
    return found


def _declared_units(gcode: str) -> Optional[Units]:
    """The units the artifact itself declares, or ``None`` if it declares none.

    Returns ``None`` when both G20 and G21 appear; that contradiction is already
    reported as ``DUPLICATE_UNITS`` and is not restated here.
    """
    inch = mm = False
    for line in parse_program(gcode):
        if line.gword(20):
            inch = True
        if line.gword(21):
            mm = True
    if inch and mm:
        return None
    if inch:
        return Units.INCH
    if mm:
        return Units.MM
    return None


def _check_unit_agreement(gcode: str, config: Mapping[str, Any]) -> List[Diagnostic]:
    """Block when the request asked for one unit system and the artifact emits another."""
    requested_raw = config.get("units")
    if requested_raw is None:
        return []
    try:
        requested = Units(requested_raw)
    except ValueError:
        # An unusable units value is a generation-config problem, not something
        # preflight can adjudicate against the artifact.
        return []

    declared = _declared_units(gcode)
    if declared is None or declared is requested:
        return []
    return [Diagnostic(
        DiagnosticSeverity.DANGER, codes.EXPORT_UNIT_MISMATCH,
        f"Unit mismatch — export requested '{requested.value}' but the program "
        f"declares {declared.gcode_word} ('{declared.value}').")]


def _check_positive_feed(gcode: str) -> List[Diagnostic]:
    """A feed move with F <= 0 cannot cut; controllers reject or stall on it.

    Only lines that *carry* an F word are examined. A feed move relying on a
    previously-set modal feed is not a preflight concern — a genuinely absent
    feed is already reported, advisorily, as ``CUT_WITHOUT_FEED``.
    """
    found: List[Diagnostic] = []
    for line in parse_program(gcode):
        if line.motion not in ("G1", "G2", "G3"):
            continue
        feed = line.word("F")
        if feed is not None and feed <= 0:
            found.append(Diagnostic(
                DiagnosticSeverity.DANGER, codes.EXPORT_NON_POSITIVE_FEED,
                f"Feed move with non-positive feed rate (F{feed:g}).", line.number))
    return found


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_export_preflight(
    gcode: str,
    config: Optional[Mapping[str, Any]] = None,
) -> ExportPreflightResult:
    """Evaluate whether ``gcode`` may be exported under the current policy.

    ``gcode`` is the artifact that would be written; ``config`` is the generation
    context that produced it — the same mapping ``build_program`` consumes
    (``machine``, ``units``, and friends). Neither argument is modified.

    All independently determinable checks run in one pass. When the artifact is
    empty every content check is vacuous, so they are skipped and named in
    ``skipped_rule_ids`` rather than silently omitted.
    """
    config = config or {}
    machine = config.get("machine")

    blocking: List[Diagnostic] = []
    advisory: List[Diagnostic] = []
    evaluated: List[str] = [RULE_EMPTY_ARTIFACT]

    empty = _check_empty(gcode)
    if empty:
        return _build(
            blocking=empty,
            advisory=[],
            evaluated=evaluated,
            skipped=[r for r in ALL_RULE_IDS if r != RULE_EMPTY_ARTIFACT],
        )

    # Reuse the validator for detection; preflight only classifies its findings.
    evaluated.append(RULE_REUSED_VALIDATOR)
    for diag in validate_program(gcode, machine):
        if diag.code in BLOCKING_CODES or codes.canonical_code(diag.code) in BLOCKING_CODES:
            blocking.append(diag)
        else:
            advisory.append(diag)

    evaluated.append(RULE_UNIT_AGREEMENT)
    blocking.extend(_check_unit_agreement(gcode, config))

    evaluated.append(RULE_NON_FINITE)
    blocking.extend(_check_non_finite(gcode))

    evaluated.append(RULE_FEED_POSITIVE)
    blocking.extend(_check_positive_feed(gcode))

    return _build(blocking, advisory, evaluated, [])


def _build(
    blocking: List[Diagnostic],
    advisory: List[Diagnostic],
    evaluated: List[str],
    skipped: List[str],
) -> ExportPreflightResult:
    """Freeze the accumulated findings into a sorted, immutable result."""
    return ExportPreflightResult(
        export_allowed=not blocking,
        blocking_findings=tuple(sorted(blocking, key=_sort_key)),
        advisory_findings=tuple(sorted(advisory, key=_sort_key)),
        policy_version=POLICY_VERSION,
        disclaimer=DISCLAIMER,
        evaluated_rule_ids=tuple(evaluated),
        skipped_rule_ids=tuple(skipped),
    )
