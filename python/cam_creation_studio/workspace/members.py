"""Shared member-list checks for selections and groups (CS-011)."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import WorkspaceError


def as_entity_ids(entity_ids: object, kind: str) -> tuple[str, ...]:
    """Return caller order exactly, or reject empty / duplicate members.

    Silent deduplication would mutate user intent, so duplicates fail instead.
    """
    if isinstance(entity_ids, (str, bytes)) or not isinstance(entity_ids, Iterable):
        raise WorkspaceError(f"{kind} entity_ids must be a sequence of IDs")
    members = tuple(entity_ids)
    if not members:
        raise WorkspaceError(f"{kind} is empty")
    if len(members) != len(set(members)):
        raise WorkspaceError(f"{kind} contains duplicate entity IDs")
    return members
