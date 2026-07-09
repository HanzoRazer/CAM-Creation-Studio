"""Advisory feeds/speeds calculator and conservative presets.

Re-exports the public surface (calculator, machine and material presets) so
callers can import from the package directly. ``FeedsResult`` and ``Machine``
are deprecated aliases of the canonical ``FeedRecommendation`` and
``MachineProfile`` and are kept importable for compatibility.
"""

from .calculator import (  # noqa: F401
    FeedDiagnostic,
    FeedRecommendation,
    FeedsResult,
    calculate_feeds,
)
from .machines import (  # noqa: F401
    Machine,
    MachineProfile,
    get_machine,
    list_machines,
)
from .materials import Material, get_material, list_materials  # noqa: F401

__all__ = [
    "calculate_feeds",
    "FeedRecommendation",
    "FeedsResult",
    "FeedDiagnostic",
    "MachineProfile",
    "Machine",
    "get_machine",
    "list_machines",
    "Material",
    "get_material",
    "list_materials",
]
