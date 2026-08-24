"""Deterministic workspace identifiers (CS-011).

Two ID kinds, documented so they are not later treated as interchangeable:

* :func:`make_workspace_entity_id` — deterministic **identity of imported
  geometry**. The same collection always yields the same refs.
* :func:`make_workspace_object_id` — deterministic **workspace-object
  identity generated from creation context** (kind, name, members, and how
  many objects of that kind already exist). Equivalent helper sequences
  produce equivalent IDs. Renaming or reconstructing a selection does not
  automatically preserve its ID.

Neither path uses :func:`~cam_creation_studio.shared.ids.new_id` / uuid4.
"""

from __future__ import annotations

from ..shared.ids import stable_id


def make_workspace_entity_id(
    entity_index: int,
    handle: str | None,
    ordinal: int | None,
) -> str:
    """Stable ID for the retained entity at ``entity_index``.

    ``handle`` and ``ordinal`` come from source provenance when present. An
    absent handle still produces a deterministic ID because the index is
    unique within the collection. Source-ordinal gaps do not collide: the
    index, not the ordinal, is the unique component.
    """
    return stable_id(
        entity_index,
        handle or "",
        "" if ordinal is None else ordinal,
        prefix="geom-",
    )


def make_workspace_object_id(
    kind: str,
    name: str,
    *member_ids: str,
    existing_count: int,
) -> str:
    """Stable ID for a selection, group, or operation at creation time.

    ``existing_count`` is the number of objects of this kind already on the
    workspace. It makes the ID deterministic for a given construction
    sequence, not content-addressed in the :class:`GeometryRef` sense.
    """
    return stable_id(kind, name, *member_ids, existing_count, prefix=f"{kind}-")
