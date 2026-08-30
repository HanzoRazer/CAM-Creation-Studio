"""CS-014 constitutional boundaries: advisory recommendation, not execution."""

from __future__ import annotations

import dataclasses
import inspect

from cam_creation_studio.operations.models import (
    OperationBinding,
    OperationFeedRecommendation,
)
from cam_creation_studio.operations.plan import OperationPlan
from cam_creation_studio.operations.recommendations import (
    recommend_feeds_speeds,
    replace_feed_recommendation,
)
from cam_creation_studio.operations.summary import FeedRecommendationSummary
from cam_creation_studio.workspace.models import GeometryWorkspace

_FORBIDDEN = (
    "stepdown",
    "stepover",
    "pass_count",
    "toolpath",
    "lead_in",
    "lead_out",
    "tabs",
    "compensation",
    "gcode",
    "postprocessor",
    "machine_ready",
    "safe",
    "approved",
    "doc_mm",
    "woc_mm",
)


def test_wrapper_has_no_execution_or_readiness_fields():
    names = {field.name for field in dataclasses.fields(OperationFeedRecommendation)}
    for forbidden in _FORBIDDEN:
        assert forbidden not in names


def test_plan_has_no_readiness_fields():
    names = {field.name for field in dataclasses.fields(OperationPlan)}
    for forbidden in _FORBIDDEN:
        assert forbidden not in names
    assert "recommendations" in names


def test_binding_still_has_no_machine_id():
    names = {field.name for field in dataclasses.fields(OperationBinding)}
    assert "machine_id" not in names
    assert "machine_profile_id" not in names
    assert "spindle_rpm" not in names


def test_recommend_signature_does_not_accept_engagement():
    parameters = set(inspect.signature(recommend_feeds_speeds).parameters)
    for forbidden in _FORBIDDEN:
        assert forbidden not in parameters
    assert parameters == {
        "plan", "definition_id", "machine_profile_id", "spindle_rpm", "id",
    }
    replace_params = set(inspect.signature(replace_feed_recommendation).parameters)
    for forbidden in _FORBIDDEN:
        assert forbidden not in replace_params


def test_summary_has_no_readiness_fields():
    names = {field.name for field in dataclasses.fields(FeedRecommendationSummary)}
    for forbidden in _FORBIDDEN:
        assert forbidden not in names


def test_workspace_does_not_own_recommendations():
    names = {field.name for field in dataclasses.fields(GeometryWorkspace)}
    assert "recommendations" not in names
    assert "machine_profile_id" not in names
