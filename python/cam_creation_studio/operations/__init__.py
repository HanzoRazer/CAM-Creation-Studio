"""Manufacturing operation definitions (CS-012).

Extends CS-011 :class:`~cam_creation_studio.workspace.models.OperationIntent`
with geometry-relative planning parameters. This package records *what*
operation the user intends. It does not assign tools or materials, compute
feeds/speeds, generate toolpaths, or emit G-code.
"""

from __future__ import annotations

from .enums import ContourRelation, CutDirection, SlotRelation
from .errors import OperationDefinitionError
from .models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationDefinition,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
    definition_type_name,
)

__all__ = [
    "ContourDefinition",
    "ContourRelation",
    "CutDirection",
    "DrillDefinition",
    "EngraveDefinition",
    "OperationDefinition",
    "OperationDefinitionError",
    "PocketDefinition",
    "ReferenceDefinition",
    "SlotDefinition",
    "SlotRelation",
    "definition_type_name",
]
