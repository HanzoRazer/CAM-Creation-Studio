"""Bind a local review record to one plan digest and the local policy.

A fixture review exercises this binding. It is not a human approval, and
``experimental: false`` cannot promote it into one. Admission disposition is
not a review.
"""

from __future__ import annotations

from . import codes
from .compatibility import policy_digest
from .models import Refusal, ReviewRecord


def bind_review(
    review: ReviewRecord | None,
    plan_digest_value: str,
) -> Refusal | None:
    """Return a refusal when the review does not cover this exact plan."""
    if review is None:
        return Refusal(
            codes.REVIEW_REQUIRED,
            "admission to human review is not approval of this plan; "
            "a review of the exact plan digest is required",
        )
    if review.decision != "accepted":
        return Refusal(
            codes.REVIEW_REQUIRED,
            "the review decision does not accept this plan",
        )
    if not review.experimental or review.authority != "fixture_binding_only":
        return Refusal(
            codes.POLICY_UNSUPPORTED,
            "no human-review authority is configured; a non-fixture review "
            "cannot be verified",
        )
    if review.policy_digest != policy_digest():
        return Refusal(
            codes.POLICY_UNSUPPORTED,
            "review policy digest does not match the local policy",
        )
    if review.plan_digest != plan_digest_value:
        return Refusal(
            codes.PLAN_CHANGED,
            "review is bound to a different plan digest",
        )
    return None
