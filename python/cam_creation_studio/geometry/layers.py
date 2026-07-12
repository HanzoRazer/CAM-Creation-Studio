"""Layer utilities over an imported collection (CS-008).

Layer names are *source evidence* preserved verbatim from the DXF; nothing here
interprets them (no inside/outside, no operation mapping). These helpers only
group and index entities by the layer they arrived on.
"""

from __future__ import annotations

from typing import Dict, List

from .models import Entity, GeometryCollection


def layer_names(collection: GeometryCollection) -> List[str]:
    """Sorted, de-duplicated layer names present in the collection."""
    return collection.layers


def by_layer(collection: GeometryCollection) -> Dict[str, List[Entity]]:
    """Group entities by layer name, preserving source order within each layer."""
    grouped: Dict[str, List[Entity]] = {}
    for entity in collection.entities:
        grouped.setdefault(entity.layer, []).append(entity)
    return grouped


def on_layer(collection: GeometryCollection, layer: str) -> List[Entity]:
    """Entities on a specific ``layer``, in source order."""
    return [e for e in collection.entities if e.layer == layer]
