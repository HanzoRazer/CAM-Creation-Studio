"""Canonical calculator integration for advisory recommendations (CS-014)."""

from __future__ import annotations

import pytest

from cam_creation_studio.feeds_speeds.calculator import (
    ADVISORY_ONLY,
    RPM_EXCEEDS_MACHINE_LIMIT,
    calculate_feeds,
)
from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.operations.bindings import bind_operation
from cam_creation_studio.operations.builder import (
    define_contour,
    define_drill,
    define_pocket,
    define_slot,
)
from cam_creation_studio.operations.plan import build_operation_plan
from cam_creation_studio.operations.recommendations import calculate_advisory_feeds
from cam_creation_studio.operations.resolution import resolve_recommendation_inputs
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.models import OperationKind
from cam_creation_studio.workspace.operations import assign_operation
from cam_creation_studio.workspace.selections import create_selection


def _workspace_with(*kinds: OperationKind):
    line = Line2D(start=Point(0, 0), end=Point(10, 0))
    workspace = build_workspace(GeometryCollection(entities=[line]))
    entity_id = workspace.geometry_refs[0].id
    workspace = create_selection(
        workspace, "profile", [entity_id], id="sel-1")
    for kind in kinds:
        workspace = assign_operation(
            workspace, kind.value, kind, "sel-1", id=f"op-{kind.value}")
    return workspace


def test_adapter_matches_direct_calculator_invocation():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000)
    adapted = calculate_advisory_feeds(inputs)
    direct = calculate_feeds(
        tool_diameter_mm=inputs.tool.diameter_mm,
        flutes=inputs.tool.flutes,
        spindle_rpm=12000,
        material="hardwood",
        max_rpm=inputs.machine.max_rpm,
    )
    assert adapted == direct
    assert adapted.diagnostics == direct.diagnostics


def test_adapter_does_not_pass_doc_woc_or_power_limits(monkeypatch):
    captured: dict = {}
    original = calculate_feeds

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", spy)
    workspace = _workspace_with(OperationKind.POCKET)
    definition = define_pocket(workspace, "op-pocket", 20.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000)
    calculate_advisory_feeds(inputs)
    assert "doc_mm" not in captured
    assert "woc_mm" not in captured
    assert "feed_override" not in captured
    assert "max_power_kw" not in captured
    assert captured["spindle_rpm"] == 12000
    assert captured["material"] == "hardwood"


@pytest.mark.parametrize("kind,builder", [
    (OperationKind.CONTOUR, lambda ws: define_contour(ws, "op-contour", 6.0, id="d1")),
    (OperationKind.POCKET, lambda ws: define_pocket(ws, "op-pocket", 20.0, id="d1")),
    (OperationKind.SLOT, lambda ws: define_slot(ws, "op-slot", 4.0, id="d1")),
])
def test_no_operation_kind_infers_width_of_cut(kind, builder, monkeypatch):
    captured: dict = {}
    original = calculate_feeds

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", spy)
    workspace = _workspace_with(kind)
    definition = builder(workspace)
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    inputs = resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000)
    rec = calculate_advisory_feeds(inputs)
    assert "woc_mm" not in captured
    assert rec.material_removal_rate is None
    assert rec.chip_thinning_factor == 1.0


def test_engagement_dependent_fields_remain_none_without_doc_woc():
    workspace = _workspace_with(OperationKind.POCKET)
    definition = define_pocket(workspace, "op-pocket", 20.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    rec = calculate_advisory_feeds(resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000))
    assert rec.material_removal_rate is None
    assert rec.spindle_power_kw is None
    assert rec.spindle_power_hp is None
    assert rec.torque_nm is None
    assert rec.power_w is None


def test_odd_binding_is_still_calculable():
    workspace = _workspace_with(OperationKind.DRILL)
    definition = define_drill(workspace, "op-drill", 10.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    rec = calculate_advisory_feeds(resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000))
    assert rec.feed_rate > 0
    assert any(item.code == ADVISORY_ONLY for item in rec.diagnostics)


def test_rpm_limit_warning_is_preserved_not_raised():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    rec = calculate_advisory_feeds(resolve_recommendation_inputs(
        plan, "d1", "desktop3018", 18000))
    codes = [item.code for item in rec.diagnostics]
    assert ADVISORY_ONLY in codes
    assert RPM_EXCEEDS_MACHINE_LIMIT in codes
    assert any("exceeds the machine maximum" in warning for warning in rec.warnings)


def test_requested_rpm_is_not_replaced_by_machine_ceiling():
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    rec = calculate_advisory_feeds(resolve_recommendation_inputs(
        plan, "d1", "genericCncRouter", 12000.12345))
    assert rec.rpm != 18000.0
    assert rec.rpm == pytest.approx(12000.123, abs=0.001)


def test_machine_without_max_rpm_omits_ceiling_kwarg(monkeypatch):
    captured: dict = {}
    original = calculate_feeds

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        "cam_creation_studio.operations.recommendations.calculate_feeds", spy)
    workspace = _workspace_with(OperationKind.CONTOUR)
    definition = define_contour(workspace, "op-contour", 6.0, id="d1")
    plan = bind_operation(
        build_operation_plan(workspace, (definition,)),
        "d1", "endmill_1_4", "hardwood", id="b1")
    calculate_advisory_feeds(resolve_recommendation_inputs(
        plan, "d1", "genericLaser", 12000))
    assert "max_rpm" not in captured
