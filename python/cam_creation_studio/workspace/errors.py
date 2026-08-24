"""Structural errors for the geometry workspace (CS-011).

Broken IDs, dangling references, unknown versions or operation kinds, and
malformed workspace documents are programming/document errors — not advisory
import findings and not machining judgements. One exception type is the
authority; helpers, deserialization, and :func:`validate_workspace` all raise
it. There is no second findings-based validation path.
"""

from __future__ import annotations


class WorkspaceError(Exception):
    """A workspace document or operation is structurally invalid."""
