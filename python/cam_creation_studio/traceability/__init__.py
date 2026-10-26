"""Traceable planning boundary for CAM Creation Studio.

Python owns verification, fingerprints, and governed-export checks. This
package does not plan contours and does not authorize machining.
"""

from __future__ import annotations

from .codes import REASON_CODES
from .compatibility import EXPERIMENTAL_BANNER
from .service import (
    classify_generate_document,
    evaluate_explicit_motion_export,
    evaluate_governed_generate,
    evaluate_verified_motion_export,
    export_governed_package,
    run_witness,
    verify_package,
    write_offline_export,
)

__all__ = [
    "EXPERIMENTAL_BANNER",
    "REASON_CODES",
    "classify_generate_document",
    "evaluate_explicit_motion_export",
    "evaluate_governed_generate",
    "evaluate_verified_motion_export",
    "export_governed_package",
    "run_witness",
    "verify_package",
    "write_offline_export",
]
