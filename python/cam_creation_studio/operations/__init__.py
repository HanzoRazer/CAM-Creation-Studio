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
from .plan import (
    OPERATION_PLAN_VERSION,
    OperationPlan,
    add_definition,
    build_operation_plan,
    remove_definition,
    replace_definition,
    validate_operation_plan,
)
from .serialization import (
    operation_definition_from_dict,
    operation_definition_to_dict,
    operation_plan_from_dict,
    operation_plan_from_json,
    operation_plan_to_dict,
    operation_plan_to_json,
)
from .summary import OperationPlanSummary, summarize_operation_plan
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
    "OPERATION_PLAN_VERSION",
    "ContourDefinition",
    "ContourRelation",
    "CutDirection",
    "DrillDefinition",
    "EngraveDefinition",
    "OperationDefinition",
    "OperationDefinitionError",
    "OperationPlan",
    "OperationPlanSummary",
    "PocketDefinition",
    "ReferenceDefinition",
    "SlotDefinition",
    "SlotRelation",
    "add_definition",
    "build_operation_plan",
    "define_contour",
    "define_drill",
    "define_engrave",
    "define_pocket",
    "define_reference",
    "define_slot",
    "definition_type_name",
    "make_operation_definition_id",
    "operation_definition_from_dict",
    "operation_definition_to_dict",
    "operation_plan_from_dict",
    "operation_plan_from_json",
    "operation_plan_to_dict",
    "operation_plan_to_json",
    "remove_definition",
    "replace_definition",
    "require_intent_kind",
    "resolve_intent",
    "summarize_operation_plan",
    "validate_nonnegative_optional_distance",
    "validate_operation_definition",
    "validate_operation_definitions",
    "validate_operation_plan",
    "validate_optional_positive_distance",
    "validate_positive_distance",
]
