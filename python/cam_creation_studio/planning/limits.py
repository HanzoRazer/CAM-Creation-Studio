"""Local limits for the rectangular centerline planner.

These constants are code. A request, planner-input document, or CLI flag
cannot raise them. Traceability records the same numbers in its policy
digest so a limit change invalidates a fixture review.
"""

from __future__ import annotations

PLANNER_ID = "creation-studio.rectangle-centerline"
PLANNER_VERSION = "1"
MOTION_SOURCE = "rectangular_centerline_planner"
INPUT_VERSION = "creation-studio.rectangular-planner-input/1"
GENERATED_PLAN_VERSION = "creation-studio.traceable-plan/2"
GENERATED_MANIFEST_VERSION = "creation-studio.traceable-export-manifest/2"

# One pass is a plunge, four cuts, and a retract. No joining travel move.
MOTIONS_PER_PASS = 6
MAX_DEPTH_LEVELS = 8
MAX_MOTIONS = 18
MAX_PLANNER_INPUT_BYTES = 256 * 1024

RECTANGULAR_CENTERLINE_AVAILABLE = True
