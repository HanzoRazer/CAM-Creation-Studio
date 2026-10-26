"""Producer trust for an admission document.

A digest proves that bytes did not change. It does not prove who produced
them. This repository has no operational publication or review anchor, so
operational trust always fails. Offline verification may accept only the
locally pinned synthetic fixture producer, and that acceptance is not
operational trust.

``advisory_allowed``, ``advisory_authority_granted``, ``approved``, and
``pin_status`` are not consulted.
"""

from __future__ import annotations

from . import codes
from .compatibility import (
    FIXTURE_PRODUCER,
    OPERATIONAL_TRUST_CONFIGURED,
)
from .models import AdmissionRecord, Refusal


def assess_producer(
    admission: AdmissionRecord, *, mode: str,
) -> tuple[str | None, Refusal | None]:
    """Return ``(trust_label, refusal)``.

    ``mode`` is selected by the local caller. An artifact cannot pass it in.
    """
    if mode not in ("offline", "operational"):
        return None, Refusal(
            codes.POLICY_UNSUPPORTED, f"unknown verification mode {mode!r}")
    if mode == "operational":
        # A local boolean is not a publisher. Forcing it on does not create trust.
        return None, Refusal(
            codes.UNTRUSTED_ADMISSION,
            "no operational publication or review mechanism is configured "
            f"(operational_trust_configured={OPERATIONAL_TRUST_CONFIGURED})",
        )
    if admission.producer_id != FIXTURE_PRODUCER:
        return None, Refusal(
            codes.UNTRUSTED_ADMISSION,
            "admission producer is not a locally pinned offline fixture producer",
        )
    return "offline_fixture", None
