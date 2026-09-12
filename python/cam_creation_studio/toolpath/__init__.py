"""Controller-neutral planned motion (CS-016).

Canonical cutter-center toolpaths. Preview is a projection; G-code Move /
ArcMove are downstream translation types. This package does not generate
machining paths from geometry.
"""

from __future__ import annotations

from .builders import (
    build_toolpath_plan,
    make_arc_motion,
    make_linear_motion,
    make_operation_path,
    make_toolpath_plan,
)
from .enums import MotionKind, ToolpathStatus
from .errors import ToolpathError
from .fingerprint import (
    definition_digest,
    geometry_digest,
    geometry_digest_for_ids,
    recommendation_digest,
    strategy_fingerprint,
    upstream_fingerprint,
)
from .ids import (
    make_motion_id,
    make_operation_path_id,
    make_path_id,
    make_toolpath_id,
)
from .models import (
    TOOLPATH_PLAN_V1,
    TOOLPATH_PLAN_VERSION,
    ArcMotion,
    LinearMotion,
    MotionSegment,
    OperationPath,
    ToolpathPlan,
    ToolpathStrategy,
)
from .preview_adapter import preview_projection_loss, toolpath_to_preview
from .serialization import (
    toolpath_from_dict,
    toolpath_from_json,
    toolpath_to_dict,
    toolpath_to_json,
)
from .status import toolpath_status
from .validation import validate_toolpath_plan

__all__ = [
    "TOOLPATH_PLAN_V1",
    "TOOLPATH_PLAN_VERSION",
    "ArcMotion",
    "LinearMotion",
    "MotionKind",
    "MotionSegment",
    "OperationPath",
    "ToolpathError",
    "ToolpathPlan",
    "ToolpathStatus",
    "ToolpathStrategy",
    "build_toolpath_plan",
    "definition_digest",
    "geometry_digest",
    "geometry_digest_for_ids",
    "make_arc_motion",
    "make_linear_motion",
    "make_motion_id",
    "make_operation_path",
    "make_operation_path_id",
    "make_path_id",
    "make_toolpath_id",
    "make_toolpath_plan",
    "preview_projection_loss",
    "recommendation_digest",
    "strategy_fingerprint",
    "toolpath_from_dict",
    "toolpath_from_json",
    "toolpath_status",
    "toolpath_to_dict",
    "toolpath_to_json",
    "toolpath_to_preview",
    "upstream_fingerprint",
    "validate_toolpath_plan",
]
