"""Import diagnostics for the geometry subsystem (CS-008).

Importing a DXF is *advisory*: no entity is ever silently discarded. When the
importer meets something it cannot fully represent — an unsupported entity type,
a zero-length line, an unknown unit — it records a :class:`GeometryDiagnostic`
rather than dropping the geometry on the floor. Diagnostics reuse the shared
:class:`~cam_creation_studio.enums.DiagnosticSeverity` scale so callers reason
about geometry findings exactly as they do about G-code validator findings.

Every diagnostic carries a stable string ``code`` (see the constants below) so
tests and consumers match on a symbol, never a prose message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
)


@dataclass(frozen=True, slots=True)
class GeometryDiagnostic:
    """One advisory finding raised while importing geometry.

    ``entity_type`` / ``handle`` / ``layer`` locate the finding in the source
    DXF when applicable; all are optional so file-level findings (empty file,
    unknown units) can omit them.
    """

    severity: DiagnosticSeverity
    code: str
    message: str
    entity_type: Optional[str] = None
    handle: Optional[str] = None
    layer: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.severity, DiagnosticSeverity):
            object.__setattr__(self, "severity", DiagnosticSeverity(self.severity))

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "entity_type": self.entity_type,
            "handle": self.handle,
            "layer": self.layer,
        }


def info(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.INFO, code, message, **loc)


def warning(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.WARNING, code, message, **loc)


def danger(code: str, message: str, **loc: Optional[str]) -> GeometryDiagnostic:
    return GeometryDiagnostic(DiagnosticSeverity.DANGER, code, message, **loc)
