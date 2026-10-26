"""Defects in the traceability boundary.

Verification failures are :class:`~cam_creation_studio.traceability.models.Refusal`
values. This exception is reserved for programming defects and must not be
turned into a successful verification.
"""

from __future__ import annotations


class TraceabilityDefect(RuntimeError):
    """Broken traceability code, not a rejected document."""
