"""Structural status of a stored toolpath versus current inputs (CS-016).

Status is informational. ``STALE`` means fingerprints no longer match. It
is not a claim that the path is unsafe, and it does not regenerate motion.
"""

from __future__ import annotations

from .enums import ToolpathStatus
from .models import ToolpathPlan


def toolpath_status(
    plan: ToolpathPlan | None,
    current_upstream_fingerprint: str,
) -> ToolpathStatus:
    """Describe a stored plan against a freshly computed upstream fingerprint."""
    if plan is None:
        return ToolpathStatus.MISSING
    if plan.upstream_fingerprint == current_upstream_fingerprint:
        return ToolpathStatus.CURRENT
    return ToolpathStatus.STALE
