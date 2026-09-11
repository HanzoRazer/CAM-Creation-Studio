"""Structural errors for controller-neutral toolpath documents (CS-016).

Broken IDs, malformed motion, unknown versions, and invalid numeric fields
are programming/document errors — not machining judgements and not
machine-readiness claims.
"""

from __future__ import annotations


class ToolpathError(ValueError):
    """Invalid controller-neutral toolpath structure."""
