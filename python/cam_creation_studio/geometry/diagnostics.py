"""Import diagnostics for the geometry subsystem (CS-008).

Importing a DXF is *advisory*: no entity is ever silently discarded. When the
importer meets something it cannot fully represent — an unsupported entity type,
a zero-length line, an unknown unit — it records a :class:`GeometryDiagnostic`
rather than dropping the geometry on the floor. Diagnostics reuse the shared
:class:`~cam_creation_studio.enums.DiagnosticSeverity` scale so callers reason
about geometry findings exactly as they do about G-code validator findings.

Every diagnostic carries a stable string ``code`` (see the constants below) so
tests and consumers match on a symbol, never a prose message.

Loss evidence
-------------
A diagnostic answers "something happened here". Two additive fields make it
answer "and what did it cost":

* ``recoverable`` — whether enough evidence survives to reconstruct the source.
  ``None`` means the question does not apply (an advisory that costs nothing).
* ``metadata`` — the structured particulars: counts, degrees, source normals,
  tolerances. Never prose; prose belongs in ``message``.

This deliberately does **not** introduce a separate loss-record type. The
geometry subsystem already owns import diagnostics and already carries the
entity-level context (type, handle, layer) any loss report needs; a parallel
model would split that ownership for no gain.

:data:`LOSS_CODES` names the codes that mean *source information did not
survive*, which is what distinguishes real loss from routine normalization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..enums import DiagnosticSeverity

# --- Canonical geometry diagnostic codes ----------------------------------- #
UNSUPPORTED_ENTITY = "UNSUPPORTED_ENTITY"
MISSING_LAYER = "MISSING_LAYER"
ZERO_LENGTH_LINE = "ZERO_LENGTH_LINE"
ZERO_RADIUS = "ZERO_RADIUS"
INVALID_SPLINE = "INVALID_SPLINE"
UNKNOWN_UNITS = "UNKNOWN_UNITS"
EMPTY_FILE = "EMPTY_FILE"
DUPLICATE_HANDLE = "DUPLICATE_HANDLE"
DEGENERATE_POLYLINE = "DEGENERATE_POLYLINE"
# A polyline segment carried a non-zero bulge (an arc). We keep the vertices but
# flatten the arc to a chord, so the shape changes — surfaced, never silent.
POLYLINE_BULGE_IGNORED = "POLYLINE_BULGE_IGNORED"

# --- Fidelity codes (CS-008 remediation) ----------------------------------- #
# The spline and elevation codes are reserved in this evidence increment; the
# importer begins emitting them in the increments that follow. Naming them here
# keeps the registry the single place the vocabulary is defined.
#
# There is deliberately no OCS_TRANSFORM_APPLIED code: a transform that succeeds
# is correct importer behavior, not a defect, and recording it as a diagnostic
# would train readers to ignore the ones that matter. Success is evidenced in
# entity/import metadata; only failure earns a diagnostic.
FIT_POINT_SPLINE_UNREPRESENTED = "FIT_POINT_SPLINE_UNREPRESENTED"
RATIONAL_SPLINE_WEIGHTS_DROPPED = "RATIONAL_SPLINE_WEIGHTS_DROPPED"
LWPOLYLINE_ELEVATION_DROPPED = "LWPOLYLINE_ELEVATION_DROPPED"
EMPTY_SPLINE_GEOMETRY = "EMPTY_SPLINE_GEOMETRY"
# The two OCS codes are live — F1 landed in #14 and its hardening in #16 — and
# they are not interchangeable.
#
# An entity carried a non-default extrusion whose OCS -> WCS transform could not be
# obtained or applied: no ``ocs()`` where one is required, ``ocs()`` raised, or the
# mapper raised when applied. Coordinates are left untransformed and may therefore
# be misplaced. Successful normalization is ordinary behaviour and is NOT reported
# here — see NON_PLANAR_GEOMETRY for the transform that succeeds but loses fidelity.
OCS_TRANSFORM_FAILED = "OCS_TRANSFORM_FAILED"
# The OCS -> WCS transform SUCCEEDED and every coordinate is correctly placed, but
# the result does not lie parallel to the WCS XY plane, so the 2D model cannot
# represent it faithfully: a tilted circle projects to an ellipse, a tilted arc's
# sweep is not an XY sweep, and a tilted vertex chain's XY projection is
# foreshortened. Nothing failed and nothing is misplaced; what is lost is the
# guarantee that reading the entity as a planar profile recovers the authored shape.
NON_PLANAR_GEOMETRY = "NON_PLANAR_GEOMETRY"

CANONICAL_CODES = (
    UNSUPPORTED_ENTITY,
    MISSING_LAYER,
    ZERO_LENGTH_LINE,
    ZERO_RADIUS,
    INVALID_SPLINE,
    UNKNOWN_UNITS,
    EMPTY_FILE,
    DUPLICATE_HANDLE,
    DEGENERATE_POLYLINE,
    POLYLINE_BULGE_IGNORED,
    FIT_POINT_SPLINE_UNREPRESENTED,
    RATIONAL_SPLINE_WEIGHTS_DROPPED,
    OCS_TRANSFORM_FAILED,
    NON_PLANAR_GEOMETRY,
    LWPOLYLINE_ELEVATION_DROPPED,
    EMPTY_SPLINE_GEOMETRY,
)

# Codes meaning source information did not survive the import. Everything else
# is an observation about geometry that arrived intact.
#
# The two OCS codes fall on opposite sides of this line, which is the clearest
# illustration of what the line is:
#
# * ``OCS_TRANSFORM_FAILED`` is absent on purpose — it reports that a correction
#   could not be applied, a correctness failure rather than a fidelity cost.
# * ``NON_PLANAR_GEOMETRY`` is present. The transform succeeded and no coordinate
#   is misplaced, but the entity's *plane* is not representable here and the
#   models store no extrusion, so the authored orientation is genuinely gone. A
#   tilted circle read back as a Circle2D is not the circle that was drawn.
LOSS_CODES = frozenset({
    UNSUPPORTED_ENTITY,
    POLYLINE_BULGE_IGNORED,
    FIT_POINT_SPLINE_UNREPRESENTED,
    RATIONAL_SPLINE_WEIGHTS_DROPPED,
    LWPOLYLINE_ELEVATION_DROPPED,
    EMPTY_SPLINE_GEOMETRY,
    NON_PLANAR_GEOMETRY,
})


def is_loss(code: str) -> bool:
    """True when ``code`` means source information did not survive the import."""
    return code in LOSS_CODES


@dataclass(frozen=True, slots=True)
class GeometryDiagnostic:
    """One advisory finding raised while importing geometry.

    ``entity_type`` / ``handle`` / ``layer`` locate the finding in the source
    DXF when applicable; all are optional so file-level findings (empty file,
    unknown units) can omit them.

    ``recoverable`` and ``metadata`` carry loss evidence. ``recoverable`` is
    ``None`` for findings that cost nothing, ``True`` when enough survives to
    reconstruct the source, ``False`` when information is gone. ``metadata``
    holds the structured particulars — counts, degrees, normals, tolerances —
    so a consumer never has to parse ``message``.

    Note that ``metadata`` makes instances unhashable, as a mutable-mapping
    field always does. Diagnostics are collected in lists and matched on
    ``code``; nothing in the subsystem puts them in a set.
    """

    severity: DiagnosticSeverity
    code: str
    message: str
    entity_type: Optional[str] = None
    handle: Optional[str] = None
    layer: Optional[str] = None
    recoverable: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.severity, DiagnosticSeverity):
            object.__setattr__(self, "severity", DiagnosticSeverity(self.severity))

    @property
    def is_loss(self) -> bool:
        """True when this finding records information that did not survive."""
        return self.code in LOSS_CODES

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "entity_type": self.entity_type,
            "handle": self.handle,
            "layer": self.layer,
            "recoverable": self.recoverable,
            "metadata": dict(self.metadata),
        }


def info(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.INFO, code, message, **loc)


def warning(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.WARNING, code, message, **loc)


def danger(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.DANGER, code, message, **loc)


def loss(
    code: str,
    message: str,
    *,
    recoverable: bool,
    metadata: Optional[Dict[str, Any]] = None,
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
    **loc: Optional[str],
) -> GeometryDiagnostic:
    """Build a diagnostic recording that source information did not survive.

    ``recoverable`` and ``metadata`` are mandatory-by-signature rather than
    optional, because a loss finding that cannot say what was lost is barely
    better than silence — which is the whole failure mode this exists to close.
    """
    return GeometryDiagnostic(
        severity, code, message,
        recoverable=recoverable, metadata=dict(metadata or {}), **loc,
    )
