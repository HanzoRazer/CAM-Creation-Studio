"""Fixture-only review bytes.

This helper is for tests. Planning and export do not call it, and the
review it builds is not human approval.
"""

from __future__ import annotations

import json

from cam_creation_studio.traceability.compatibility import (
    REVIEW_VERSION,
    policy_digest,
)


def fixture_review_bytes(plan_digest: str, **overrides) -> bytes:
    """Bind one digest to the live local policy. Fixture authority only."""
    document = {
        "authority": "fixture_binding_only",
        "contract_version": REVIEW_VERSION,
        "decision": "accepted",
        "experimental": True,
        "plan_digest": plan_digest,
        "policy_digest": policy_digest(),
        "recorded_at": "2026-10-26T18:00:00Z",
        "review_id": "revw-rectangle-fixture-1",
        "reviewer_ref": "synthetic-fixture-reviewer",
    }
    document.update(overrides)
    return (json.dumps(document, sort_keys=True) + "\n").encode("utf-8")
