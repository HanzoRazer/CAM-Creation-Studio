"""Deterministic operation-definition identifiers (CS-012).

IDs are a creation-context identity, matching CS-011 workspace objects:
kind, referenced intent, and how many definitions already exist. Equivalent
helper sequences therefore produce equivalent IDs. ``uuid4`` / ``new_id()``
are not used.
"""

from __future__ import annotations

from ..shared.ids import stable_id


def make_operation_definition_id(
    definition_type: str,
    intent_id: str,
    *,
    existing_count: int,
) -> str:
    """Stable ID for a definition at creation time.

    ``existing_count`` is the number of definitions already on the plan (or
    ``0`` when a builder is used standalone). It makes the ID deterministic
    for a given construction sequence, not content-addressed.
    """
    return stable_id(
        definition_type, intent_id, existing_count,
        prefix=f"{definition_type}-",
    )
