"""Identifier helpers for provenance.

Domain objects will eventually need stable identities — to trace a generated
program back to the job that produced it, to diff two runs, or to key a cache.
This module centralizes id creation so the strategy can evolve in one place.

Two flavours:

* :func:`new_id` — a fresh random id (uuid4). Use for "this instance, right now".
* :func:`stable_id` — a deterministic id derived from content (uuid5). Same
  inputs always yield the same id, which is what provenance and caching want.
"""

from __future__ import annotations

import uuid

# A fixed namespace so ``stable_id`` values are reproducible across processes.
_NAMESPACE = uuid.UUID("6b6d5f2a-4c1e-5a7b-9d3f-1c2e4a6b8d0f")


def new_id(prefix: str = "") -> str:
    """Return a fresh random identifier, optionally prefixed (e.g. ``move-``)."""
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value


def stable_id(*parts: object, prefix: str = "") -> str:
    """Return a deterministic id derived from ``parts``.

    The same ``parts`` always produce the same id, so this is safe for
    provenance keys and content-addressed caches.
    """
    seed = "|".join(str(p) for p in parts)
    value = uuid.uuid5(_NAMESPACE, seed).hex
    return f"{prefix}{value}" if prefix else value
