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


def make_binding_id(
    definition_id: str,
    tool_id: str,
    material_id: str,
    *,
    existing_count: int,
) -> str:
    """Stable ID for a binding at creation time.

    ``existing_count`` is the number of bindings already on the plan.
    Equivalent helper sequences therefore produce equivalent IDs.
    """
    return stable_id(
        "binding", definition_id, tool_id, material_id, existing_count,
        prefix="bind-",
    )


def make_recommendation_id(
    definition_id: str,
    binding_id: str,
    machine_profile_id: str,
    input_fingerprint: str,
) -> str:
    """Stable ID for a feed recommendation at creation time."""
    return stable_id(
        "feed-recommendation",
        definition_id,
        binding_id,
        machine_profile_id,
        input_fingerprint,
        prefix="rec-",
    )
