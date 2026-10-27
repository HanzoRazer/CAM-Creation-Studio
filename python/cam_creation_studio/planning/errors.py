"""Planner refusals.

``code`` uses the traceability reason vocabulary. This package does not
import traceability, so the adapter checks the code before it builds a
``Refusal``.
"""

from __future__ import annotations


class PlanningError(Exception):
    """A bounded planner refusal. No motion was allocated for this failure."""

    def __init__(self, code: str, detail: str) -> None:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("planning error code must be non-blank")
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("planning error detail must be non-blank")
        self.code = code
        self.detail = detail
        super().__init__(detail)
