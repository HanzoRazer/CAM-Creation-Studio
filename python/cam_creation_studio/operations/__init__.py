"""Manufacturing operation definitions (CS-012).

Extends CS-011 :class:`~cam_creation_studio.workspace.models.OperationIntent`
with geometry-relative planning parameters. This package records *what*
operation the user intends. It does not assign tools or materials, compute
feeds/speeds, generate toolpaths, or emit G-code.
"""

from __future__ import annotations

from .builder import (
    define_contour,
    define_drill,
    define_engrave,
    define_pocket,
    define_reference,
    define_slot,
)
from .enums import ContourRelation, CutDirection, SlotRelation
from .errors import OperationDefinitionError
from .ids import make_operation_definition_id
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
from .validation import (
    require_intent_kind,
    resolve_intent,
    validate_nonnegative_optional_distance,
    validate_operation_definition,
    validate_operation_definitions,
    validate_optional_positive_distance,
    validate_positive_distance,
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
    "define_contour",
    "define_drill",
    "define_engrave",
    "define_pocket",
    "define_reference",
    "define_slot",
    "definition_type_name",
    "make_operation_definition_id",
    "require_intent_kind",
    "resolve_intent",
    "validate_nonnegative_optional_distance",
    "validate_operation_definition",
    "validate_operation_definitions",
    "validate_optional_positive_distance",
    "validate_positive_distance",
]
