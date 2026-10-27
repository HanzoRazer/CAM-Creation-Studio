"""Synthetic rectangular-coupon packages for offline tests.

These are software-test values, not approved cutting data. They describe a
flat coupon, not a guitar plate or brace. Building a package does not give
it operational status.
"""

from __future__ import annotations

import json
from pathlib import Path

from .compatibility import (
    ADMISSION_CONTRACT,
    FIXTURE_PRODUCER,
    FIXTURE_VERSION,
    GEOMETRY_CONTRACT,
    PROPOSAL_CONTRACT,
    REQUEST_VERSION,
    SUBJECT_CONTRACT,
    SUPPORTED_FRAME,
    SUPPORTED_OPERATION,
    SUPPORTED_PROFILE,
    SUPPORTED_UNITS,
    VALIDATION_CONTRACT,
)
from .encoding import sha256_bytes

PACKAGE_ID = "pkg-synthetic-coupon-1"
SUBJECT_ID = "specimen-synthetic-coupon-1"
GEOMETRY_ID = "geom-coupon-rect-1"
REVISION = "rev-1"
PROPOSAL_ID = "prop-coupon-1"
VALIDATION_ID = "val-coupon-1"
ADMISSION_ID = "adm-coupon-1"
REQUEST_ID = "req-coupon-1"
FRAME_NAME = "stock-fixed rectangular coupon"

CENTER = (20.0, 15.0, 60.0, 35.0)
REMOVAL = (10.0, 5.0, 70.0, 45.0)
MAX_DEPTH_MM = 3.0
TOOL_DIAMETER_MM = 6.0
TOLERANCE_MM = 0.05
DEPTH_LEVELS = (1.0, 2.0)


def build_synthetic_package(root: Path, variant: str = "consistent") -> Path:
    """Write one immutable fixture package. ``variant`` selects a refusal case."""
    if root.exists():
        for child in root.iterdir():
            if child.is_file() and not child.is_symlink():
                child.unlink()
    root.mkdir(parents=True, exist_ok=True)
    geometry_revision = REVISION
    geometry_units = SUPPORTED_UNITS
    geometry_frame = SUPPORTED_FRAME
    subject_id = SUBJECT_ID
    proposal_package = PACKAGE_ID
    request_revision = REVISION
    request_units = SUPPORTED_UNITS
    request_frame = SUPPORTED_FRAME
    depth_levels = list(DEPTH_LEVELS)
    producer = FIXTURE_PRODUCER
    admission_proposal_id = PROPOSAL_ID
    admission_digest_override = None
    favorable = False
    workflow_origin = "imported"

    if variant == "depth":
        depth_levels = [1.0, 4.0]
    elif variant == "geometry":
        request_revision = "rev-2"
    elif variant == "admission":
        admission_proposal_id = "prop-other"
        admission_digest_override = sha256_bytes(b"other-proposal")
    elif variant == "forged_producer":
        producer = "forged-publisher"
    elif variant == "favorable":
        favorable = True
    elif variant == "units":
        geometry_units = "in"
    elif variant == "frame":
        geometry_frame = "fixture-other-frame"
    elif variant == "subject":
        subject_id = "specimen-other"
    elif variant == "package":
        proposal_package = "pkg-other"
    elif variant == "relabel":
        workflow_origin = "human_authored"
    elif variant != "consistent":
        raise ValueError(f"unknown synthetic variant {variant!r}")

    subject = {
        "artifact_id": "subject-coupon-1",
        "contract_id": SUBJECT_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "kind": "synthetic_rectangular_coupon",
        "subject_id": subject_id,
    }
    geometry = {
        "artifact_id": GEOMETRY_ID,
        "contract_id": GEOMETRY_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "coordinate_frame_id": geometry_frame,
        "geometry_id": GEOMETRY_ID,
        "kind": "rectangle",
        "revision": geometry_revision,
        "units": geometry_units,
        "x_max_mm": CENTER[2],
        "x_min_mm": CENTER[0],
        "y_max_mm": CENTER[3],
        "y_min_mm": CENTER[1],
    }
    proposal = {
        "artifact_id": PROPOSAL_ID,
        "contract_id": PROPOSAL_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "coordinate_frame_id": SUPPORTED_FRAME,
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": geometry_revision,
        "operation_type": SUPPORTED_OPERATION,
        "package_id": proposal_package,
        "proposal_id": PROPOSAL_ID,
        "subject_id": SUBJECT_ID,
        "units": SUPPORTED_UNITS,
    }
    _write(root / "subject.json", subject)
    _write(root / "geometry.json", geometry)
    _write(root / "proposal.json", proposal)
    proposal_sha = sha256_bytes((root / "proposal.json").read_bytes())
    validation = {
        "artifact_id": VALIDATION_ID,
        "contract_id": VALIDATION_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": geometry_revision,
        "package_id": proposal_package,
        "proposal_digest": proposal_sha,
        "proposal_id": PROPOSAL_ID,
        "result": "recorded_for_fixture",
        "subject_id": SUBJECT_ID,
        "validation_id": VALIDATION_ID,
    }
    _write(root / "validation.json", validation)
    validation_sha = sha256_bytes((root / "validation.json").read_bytes())
    admission = {
        "artifact_id": ADMISSION_ID,
        "contract_id": ADMISSION_CONTRACT,
        "contract_version": FIXTURE_VERSION,
        "current_state": "not_established",
        "disposition": "admitted_for_human_review",
        "geometry_id": GEOMETRY_ID,
        "geometry_revision": geometry_revision,
        "package_id": proposal_package,
        "producer_id": producer,
        "proposal_digest": admission_digest_override or proposal_sha,
        "proposal_id": admission_proposal_id,
        "subject_id": SUBJECT_ID,
        "validation_digest": validation_sha,
        "validation_id": VALIDATION_ID,
    }
    if favorable:
        admission["advisory_allowed"] = True
        admission["advisory_authority_granted"] = True
        admission["approved"] = True
        admission["pin_status"] = "approved"
    _write(root / "admission.json", admission)
    hashes = {
        "proposal": proposal_sha,
        "validation": validation_sha,
        "admission": sha256_bytes((root / "admission.json").read_bytes()),
        "geometry": sha256_bytes((root / "geometry.json").read_bytes()),
        "subject": sha256_bytes((root / "subject.json").read_bytes()),
    }
    ids = {
        "proposal": PROPOSAL_ID,
        "validation": VALIDATION_ID,
        "admission": ADMISSION_ID,
        "geometry": GEOMETRY_ID,
        "subject": "subject-coupon-1",
    }
    contracts = {
        "proposal": PROPOSAL_CONTRACT,
        "validation": VALIDATION_CONTRACT,
        "admission": ADMISSION_CONTRACT,
        "geometry": GEOMETRY_CONTRACT,
        "subject": SUBJECT_CONTRACT,
    }
    files = {
        "proposal": "proposal.json",
        "validation": "validation.json",
        "admission": "admission.json",
        "geometry": "geometry.json",
        "subject": "subject.json",
    }
    request = {
        "contract_version": REQUEST_VERSION,
        "coordinate_frame": {"id": request_frame, "name": FRAME_NAME},
        "geometry": {"id": GEOMETRY_ID, "revision": request_revision},
        "machine_profile": {"id": SUPPORTED_PROFILE},
        "operation": {
            "centerline": {
                "x_max_mm": CENTER[2],
                "x_min_mm": CENTER[0],
                "y_max_mm": CENTER[3],
                "y_min_mm": CENTER[1],
            },
            "type": SUPPORTED_OPERATION,
        },
        "package_id": PACKAGE_ID,
        "positional_tolerance_mm": TOLERANCE_MM,
        "removal_region": {
            "max_depth_mm": MAX_DEPTH_MM,
            "x_max_mm": REMOVAL[2],
            "x_min_mm": REMOVAL[0],
            "y_max_mm": REMOVAL[3],
            "y_min_mm": REMOVAL[1],
        },
        "request_id": REQUEST_ID,
        "stock": {
            "id": "stock-coupon-rect-80x50x10",
            "material_id": "synthetic-fixture-material",
            "x_mm": 80.0,
            "y_mm": 50.0,
            "z_mm": 10.0,
        },
        "strategy": {
            "clearance_mm": 5.0,
            "depth_levels_mm": depth_levels,
            "id": "strat-witness-1",
            "stepdown_mm": 1.0,
            "stock_allowance_mm": 0.0,
            "travel_height_mm": 5.0,
        },
        "subject": {"id": SUBJECT_ID},
        "tooling": {
            "diameter_mm": TOOL_DIAMETER_MM,
            "id": "tool-flat-endmill-6",
            "kind": "flat_end_mill",
            "orientation": "fixed",
        },
        "units": request_units,
        "upstream_artifacts": [
            {
                "artifact_id": ids[role],
                "contract_id": contracts[role],
                "contract_version": FIXTURE_VERSION,
                "package_ref": files[role],
                "role": role,
                "sha256": hashes[role],
            }
            for role in ("proposal", "validation", "admission", "geometry", "subject")
        ],
        "workflow_origin": workflow_origin,
    }
    _write(root / "request.json", request)
    return root


def _write(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
