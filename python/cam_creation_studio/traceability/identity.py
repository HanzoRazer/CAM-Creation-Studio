"""Bind a request to the proposal, validation, admission, subject, and geometry.

Digests compared here are the exact-byte digests already stored on the
snapshot. Documents are not reserialized in order to match a recorded hash.
"""

from __future__ import annotations

from . import codes
from .compatibility import SUPPORTED_FRAME, SUPPORTED_OPERATION, SUPPORTED_UNITS
from .models import PackageBundle, Refusal


def check_identity(bundle: PackageBundle) -> Refusal | None:
    """Return the first broken identity relationship, if any."""
    request = bundle.request
    proposal = bundle.proposal
    validation = bundle.validation
    admission = bundle.admission
    geometry = bundle.geometry
    subject = bundle.subject
    proposal_sha = bundle.snapshot.by_role("proposal").sha256
    validation_sha = bundle.snapshot.by_role("validation").sha256

    if request.package_id != proposal.package_id or request.package_id != validation.package_id or request.package_id != admission.package_id:
        return Refusal(
            codes.PACKAGE_MISMATCH,
            "package id is not consistent across the request and upstream artifacts",
        )
    if subject.subject_id != request.subject_id or proposal.subject_id != request.subject_id or validation.subject_id != request.subject_id or admission.subject_id != request.subject_id:
        return Refusal(
            codes.SUBJECT_MISMATCH,
            "subject id is not consistent across the request and upstream artifacts",
        )
    if geometry.geometry_id != request.geometry_id or proposal.geometry_id != request.geometry_id or validation.geometry_id != request.geometry_id or admission.geometry_id != request.geometry_id:
        return Refusal(
            codes.GEOMETRY_REVISION_MISMATCH,
            "geometry id is not consistent across the request and upstream artifacts",
        )
    if geometry.revision != request.geometry_revision or proposal.geometry_revision != request.geometry_revision or validation.geometry_revision != request.geometry_revision or admission.geometry_revision != request.geometry_revision:
        return Refusal(
            codes.GEOMETRY_REVISION_MISMATCH,
            "geometry revision is not consistent across the request and upstream artifacts",
        )
    if (
        geometry.x_min_mm != request.center_x_min_mm
        or geometry.y_min_mm != request.center_y_min_mm
        or geometry.x_max_mm != request.center_x_max_mm
        or geometry.y_max_mm != request.center_y_max_mm
    ):
        return Refusal(
            codes.GEOMETRY_REVISION_MISMATCH,
            "geometry coordinates do not match the requested contour",
        )
    if request.units != proposal.units or request.units != geometry.units:
        return Refusal(
            codes.UNITS_MISMATCH,
            "units are not consistent across the request, proposal, and geometry",
        )
    if request.units != SUPPORTED_UNITS:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            f"units {request.units!r} are outside the supported witness",
        )
    if request.frame_id != proposal.coordinate_frame_id or request.frame_id != geometry.coordinate_frame_id:
        return Refusal(
            codes.FRAME_MISMATCH,
            "coordinate frame is not consistent across the request, proposal, and geometry",
        )
    if request.frame_id != SUPPORTED_FRAME:
        return Refusal(
            codes.UNSUPPORTED_CAPABILITY,
            f"coordinate frame {request.frame_id!r} is outside the supported witness",
        )
    if proposal.operation_type != request.operation_type or request.operation_type != SUPPORTED_OPERATION:
        return Refusal(
            codes.PROPOSAL_BINDING_MISMATCH,
            "proposal operation does not match the requested operation",
        )
    if proposal.proposal_id != validation.proposal_id or proposal.proposal_id != admission.proposal_id:
        return Refusal(
            codes.PROPOSAL_BINDING_MISMATCH,
            "admission or validation names a different proposal",
        )
    if validation.proposal_digest != proposal_sha or admission.proposal_digest != proposal_sha:
        return Refusal(
            codes.PROPOSAL_BINDING_MISMATCH,
            "admission or validation proposal digest is not the exact proposal bytes",
        )
    if admission.validation_id != validation.validation_id or admission.validation_digest != validation_sha:
        return Refusal(
            codes.PROPOSAL_BINDING_MISMATCH,
            "admission does not bind the resolved validation artifact",
        )
    return None
