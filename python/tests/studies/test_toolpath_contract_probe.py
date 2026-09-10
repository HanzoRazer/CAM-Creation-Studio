"""CS-015 study tests — lock empirical claims of the toolpath contract probe.

Not a production API. These tests import the study script under
``tools/studies/``; production packages must not.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_STUDIES = _REPO / "tools" / "studies"
if str(_STUDIES) not in sys.path:
    sys.path.insert(0, str(_STUDIES))

import toolpath_contract_probe as probe

from cam_creation_studio.preview.toolpath_model import (
    ARC,
    CUT,
    TRAVEL,
    ToolpathSegment,
)
from cam_creation_studio.shared.geometry import Point


def _quarter_arc(clockwise: bool) -> probe.ArcMotion:
    # Radius 10 about origin: (10,0,0) → (0,10,0).
    # CCW is the short quarter; CW is the long reflex (270°).
    return probe.make_arc(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), clockwise, index=0,
        planned_feed_mm_min=400.0, geometry_ids=("geom-arc",),
    )


def _plan_with_motions(*motions: probe.StudyMotion, **kwargs) -> probe.StudyToolpathPlan:
    path = probe.make_path(tuple(motions), index=0)
    return probe.build_study_plan(
        operation_definition_id=kwargs.get("definition_id", "def-1"),
        geometry_ids=kwargs.get("geometry_ids", ("geom-a", "geom-b")),
        binding_id=kwargs.get("binding_id", "bind-1"),
        strategy=kwargs.get("strategy", probe.StudyToolpathStrategy()),
        paths=(path,),
        recommendation_id=kwargs.get("recommendation_id", "rec-1"),
        planned_feed_mm_min=kwargs.get("planned_feed_mm_min", 800.0),
    )


# --------------------------------------------------------------------------- #
# Inventory completeness (study helper agrees with the written inventory)
# --------------------------------------------------------------------------- #

def test_inventory_helper_accounts_for_existing_authorities():
    inv = probe.inventory_motion_types()
    assert inv["preview.ToolpathSegment"] == "VIEW PROJECTION"
    assert inv["models.Move"] == "TRANSLATION MODEL"
    assert inv["models.ArcMove"] == "TRANSLATION MODEL"
    assert inv["StudyToolpathPlan"] == "CANONICAL CANDIDATE"
    assert inv["geometry.Arc2D"] == "UNRELATED"


def test_existing_types_are_projected_or_rejected_not_stored():
    disp = probe.compare_motion_contracts()
    assert disp["preview.ToolpathSegment"] == "projected_into"
    assert "rejected" in disp["models.Move"]
    assert "rejected" in disp["models.ArcMove"]
    assert disp["StudyToolpathPlan"] == "selected_canonical_candidate"


# --------------------------------------------------------------------------- #
# Linear motion (Test Plan B)
# --------------------------------------------------------------------------- #

def test_linear_cycle_is_travel_cut_retract_without_gcode():
    plan = probe.linear_cycle_plan()
    motions = plan.paths[0].motions
    assert [m.kind for m in motions] == [
        probe.MotionKind.TRAVEL, probe.MotionKind.CUT, probe.MotionKind.RETRACT,
    ]
    assert motions[0].start == Point(0, 0, 5)
    assert motions[0].end == Point(0, 0, 0)
    assert motions[1].start == Point(0, 0, 0)
    assert motions[1].end == Point(20, 0, 0)
    assert motions[2].start == Point(20, 0, 0)
    assert motions[2].end == Point(20, 0, 5)
    assert probe.serialization_forbidden_hits(plan) == ()


# --------------------------------------------------------------------------- #
# Arc fidelity (Test Plan C)
# --------------------------------------------------------------------------- #

def test_ccw_quarter_arc_stores_center_radius_direction_sweep():
    arc = _quarter_arc(clockwise=False)
    assert arc.start == Point(10, 0, 0)
    assert arc.end == Point(0, 10, 0)
    assert arc.center == Point(0, 0, 0)
    assert arc.radius == pytest.approx(10.0)
    assert arc.clockwise is False
    assert arc.sweep_rad == pytest.approx(math.pi / 2)


def test_cw_quarter_request_is_a_reflex_when_endpoints_demand_it():
    # Same endpoints, clockwise → the long way (3π/2), not a tessellation.
    arc = _quarter_arc(clockwise=True)
    assert arc.clockwise is True
    assert arc.sweep_rad == pytest.approx(-3 * math.pi / 2)
    assert abs(arc.sweep_rad) > math.pi


def test_explicit_cw_and_ccw_short_quarters():
    cw = probe.make_arc(
        Point(10, 0, 0), Point(0, -10, 0), Point(0, 0, 0), True, index=1,
    )
    ccw = probe.make_arc(
        Point(10, 0, 0), Point(0, 10, 0), Point(0, 0, 0), False, index=2,
    )
    assert cw.clockwise is True
    assert cw.sweep_rad == pytest.approx(-math.pi / 2)
    assert ccw.clockwise is False
    assert ccw.sweep_rad == pytest.approx(math.pi / 2)


def test_reflex_ccw_arc():
    arc = probe.make_arc(
        Point(10, 0, 0), Point(0, -10, 0), Point(0, 0, 0), False, index=3,
    )
    assert arc.clockwise is False
    assert arc.sweep_rad == pytest.approx(3 * math.pi / 2)
    assert abs(arc.sweep_rad) > math.pi


def test_full_circle_coincident_endpoints():
    start = Point(10, 0, 0)
    arc = probe.make_arc(start, start, Point(0, 0, 0), False, index=4)
    assert arc.start == arc.end
    assert arc.sweep_rad == pytest.approx(2 * math.pi)
    cw = probe.make_arc(start, start, Point(0, 0, 0), True, index=5)
    assert cw.sweep_rad == pytest.approx(-2 * math.pi)


def test_arcs_are_not_tessellated_in_canonical_storage():
    plan = _plan_with_motions(_quarter_arc(False), _quarter_arc(True))
    blob = probe.candidate_to_dict(plan)
    forms = [m["form"] for p in blob["paths"] for m in p["motions"]]
    assert forms == ["arc", "arc"]
    for raw in blob["paths"][0]["motions"]:
        assert "center" in raw and "sweep_rad" in raw
        assert "poly" not in raw


# --------------------------------------------------------------------------- #
# Z semantics (Test Plan D)
# --------------------------------------------------------------------------- #

def test_z_kinds_distinguish_travel_plunge_cut_retract():
    h, zcut = 5.0, -3.0
    motions = (
        probe.make_linear(probe.MotionKind.TRAVEL, Point(0, 0, h), Point(4, 0, h),
                          index=0),
        probe.make_linear(probe.MotionKind.PLUNGE, Point(4, 0, h), Point(4, 0, zcut),
                          index=1, planned_feed_mm_min=200.0),
        probe.make_linear(probe.MotionKind.CUT, Point(4, 0, zcut), Point(10, 0, zcut),
                          index=2, planned_feed_mm_min=800.0),
        probe.make_linear(probe.MotionKind.RETRACT, Point(10, 0, zcut), Point(10, 0, h),
                          index=3),
    )
    kinds = [m.kind for m in motions]
    assert kinds == [
        probe.MotionKind.TRAVEL, probe.MotionKind.PLUNGE,
        probe.MotionKind.CUT, probe.MotionKind.RETRACT,
    ]
    assert motions[0].start.z == h and motions[0].end.z == h
    assert motions[1].end.z == zcut
    # Kind, not Z sign, distinguishes plunge from retract.
    assert motions[1].end.z == motions[3].start.z
    assert motions[1].kind != motions[3].kind


# --------------------------------------------------------------------------- #
# Deterministic identity (Test Plan E)
# --------------------------------------------------------------------------- #

def test_same_inputs_same_ids_order_and_bytes():
    a = probe.linear_cycle_plan()
    b = probe.linear_cycle_plan()
    assert a.id == b.id
    assert [p.id for p in a.paths] == [p.id for p in b.paths]
    assert [m.id for p in a.paths for m in p.motions] == [
        m.id for p in b.paths for m in p.motions
    ]
    assert probe.candidate_to_json(a) == probe.candidate_to_json(b)
    assert json.dumps(probe.candidate_to_dict(a), sort_keys=True) == (
        json.dumps(probe.candidate_to_dict(b), sort_keys=True)
    )


def test_round_trip_dict_preserves_plan():
    plan = probe.linear_cycle_plan()
    restored = probe.candidate_from_dict(probe.candidate_to_dict(plan))
    assert restored == plan


# --------------------------------------------------------------------------- #
# Geometry and operation lineage (Test Plan F, G, H, I)
# --------------------------------------------------------------------------- #

def test_geometry_lineage_is_ids_not_copies():
    plan = probe.linear_cycle_plan(geometry_ids=("geom-a", "geom-b"))
    assert plan.geometry_ids == ("geom-a", "geom-b")
    for motion in plan.paths[0].motions:
        assert motion.geometry_ids == ("geom-a", "geom-b")
    blob = probe.candidate_to_json(plan)
    assert "Line2D" not in blob
    assert "Arc2D" not in blob


def test_exactly_one_operation_definition_id():
    plan = probe.linear_cycle_plan(operation_definition_id="def-contour-9")
    assert plan.operation_definition_id == "def-contour-9"
    payload = probe.candidate_to_dict(plan)
    assert payload["operation_definition_id"] == "def-contour-9"
    assert "operation_definition_ids" not in payload


def test_binding_id_is_retained_on_the_plan():
    plan = probe.linear_cycle_plan(binding_id="bind-explicit")
    assert plan.binding_id == "bind-explicit"
    assert probe.candidate_to_dict(plan)["binding_id"] == "bind-explicit"


def test_recommendation_id_and_planned_feed_are_distinct():
    plan = probe.linear_cycle_plan(
        recommendation_id="rec-advisory", planned_feed_mm_min=650.0,
    )
    assert plan.recommendation_id == "rec-advisory"
    assert plan.planned_feed_mm_min == 650.0
    assert plan.recommendation_id != str(plan.planned_feed_mm_min)


# --------------------------------------------------------------------------- #
# Depth decomposition (Test Plan J)
# --------------------------------------------------------------------------- #

def test_depth_levels_do_not_rewrite_target_depth():
    target = 12.0
    levels = probe.depth_levels(target, 3.0)
    assert levels == (3.0, 6.0, 9.0, 12.0)
    assert target == 12.0
    strategy = probe.StudyToolpathStrategy(stepdown_mm=3.0)
    paths = tuple(
        probe.make_path(
            (probe.make_linear(
                probe.MotionKind.CUT, Point(0, 0, -z), Point(10, 0, -z),
                index=i, planned_feed_mm_min=800.0,
            ),),
            index=i, depth_mm=z,
        )
        for i, z in enumerate(levels)
    )
    plan = probe.build_study_plan(
        operation_definition_id="def-depth",
        geometry_ids=("geom-a",),
        binding_id="bind-1",
        strategy=strategy,
        paths=paths,
        planned_feed_mm_min=800.0,
    )
    assert [p.depth_mm for p in plan.paths] == [3.0, 6.0, 9.0, 12.0]
    # The definition's target depth is not a field we overwrite; it is not
    # even stored as a motion kind.
    assert "target_depth_mm" not in probe.candidate_to_json(plan)


# --------------------------------------------------------------------------- #
# Compensation, direction, engagement (Test Plan K, L, M)
# --------------------------------------------------------------------------- #

def test_compensation_is_planner_owned_explicit_offset():
    on = probe.compensation_rule("on", 3.0)
    inside = probe.compensation_rule("inside", 3.0)
    outside = probe.compensation_rule("outside", 3.0)
    assert on["owner"] == "planner_explicit_cutter_center"
    assert on["offset_mm"] == 0.0
    assert inside["offset_mm"] == -3.0
    assert outside["offset_mm"] == 3.0
    assert "gcode_controller_compensation" in on["not_applied_in"]


def test_cut_direction_owned_by_strategy_not_geometry():
    rule = probe.cut_direction_rule("climb", "outside")
    assert rule["owner"] == "toolpath_strategy"
    assert "geometry mutation" in rule["reversal"]


def test_engagement_has_a_single_owner():
    owners = probe.engagement_owner()
    assert {owners[k] for k in ("DOC", "WOC", "stepdown", "stepover")} == {
        "toolpath_strategy",
    }
    assert "operation_definition" in owners["not"]


# --------------------------------------------------------------------------- #
# Drill (Test Plan N)
# --------------------------------------------------------------------------- #

def test_drill_expands_to_neutral_motions_without_canned_cycles():
    strategy = probe.StudyToolpathStrategy(
        travel_height_mm=5.0, retract_height_mm=2.0, peck_depth_mm=3.0,
    )
    motions = probe.expand_drill(
        Point(8, 4, 0), target_depth_mm=6.0, strategy=strategy,
        planned_feed_mm_min=120.0, geometry_ids=("geom-hole",),
    )
    kinds = [m.kind.value for m in motions]
    assert "travel" in kinds and "plunge" in kinds and "retract" in kinds
    text = json.dumps([probe.motion_to_dict(m) for m in motions])
    for banned in ("G81", "G83", "canned", "peck-cycle", "G0", "G1"):
        assert banned not in text
    plunges = [m for m in motions if m.kind is probe.MotionKind.PLUNGE]
    assert [m.end.z for m in plunges] == [-3.0, -6.0]


# --------------------------------------------------------------------------- #
# Preview projection (Test Plan O)
# --------------------------------------------------------------------------- #

def test_preview_projection_uses_existing_toolpath_segment():
    plan = probe.linear_cycle_plan()
    segs = probe.candidate_to_preview(plan)
    assert segs and all(isinstance(s, ToolpathSegment) for s in segs)
    assert [s.type for s in segs] == [TRAVEL, CUT, TRAVEL]
    assert segs[1].end.x == 20
    assert all(s.source_command == "" for s in segs)


def test_preview_projection_collapses_kinds_and_drops_arc_center():
    arc = _quarter_arc(False)
    plan = _plan_with_motions(arc)
    segs = probe.candidate_to_preview(plan)
    assert len(segs) == 1
    assert segs[0].type == ARC
    assert not hasattr(segs[0], "center")
    assert not hasattr(segs[0], "sweep_rad")
    loss = probe.preview_projection_loss()
    assert "arc center" in loss
    assert "plunge vs retract vs travel kinds" in loss


# --------------------------------------------------------------------------- #
# G-code semantic mapping (Test Plan P)
# --------------------------------------------------------------------------- #

def test_gcode_map_is_semantic_not_text():
    table = probe.GCODE_SEMANTIC_MAP
    assert table["travel linear"] == "rapid move"
    assert table["feed linear"] == "feed move"
    assert table["clockwise arc"] == "CW arc"
    assert table["counter-clockwise arc"] == "CCW arc"
    joined = json.dumps(table)
    assert "G0 X" not in joined
    assert "G1" not in joined


# --------------------------------------------------------------------------- #
# Persistence / staleness (Test Plan Q)
# --------------------------------------------------------------------------- #

def test_label_does_not_change_strategy_fingerprint():
    a = probe.StudyToolpathStrategy(stepdown_mm=3.0, label="alpha")
    b = probe.StudyToolpathStrategy(stepdown_mm=3.0, label="beta")
    assert probe.strategy_fingerprint(a) == probe.strategy_fingerprint(b)


def test_upstream_fingerprint_reacts_to_computational_changes():
    strategy = probe.StudyToolpathStrategy(stepdown_mm=3.0)
    base = {
        "geometry_ids": ("g1",), "geometry_digest": "geo-v1",
        "definition_digest": "def-v1", "binding_id": "bind-1",
        "recommendation_digest": "rec-v1", "strategy": strategy,
    }
    fp = probe.upstream_fingerprint(**base)
    assert fp != probe.upstream_fingerprint(**{**base, "geometry_digest": "geo-v2"})
    assert fp != probe.upstream_fingerprint(**{**base, "definition_digest": "def-v2"})
    assert fp != probe.upstream_fingerprint(**{**base, "binding_id": "bind-2"})
    assert fp != probe.upstream_fingerprint(
        **{**base, "recommendation_digest": "rec-v2"})
    assert fp != probe.upstream_fingerprint(
        **{**base, "strategy": probe.StudyToolpathStrategy(stepdown_mm=2.0)})
    same_label = probe.StudyToolpathStrategy(stepdown_mm=3.0, label="other")
    assert fp == probe.upstream_fingerprint(**{**base, "strategy": same_label})


# --------------------------------------------------------------------------- #
# Constitutional negatives (Test Plan R)
# --------------------------------------------------------------------------- #

def test_canonical_serialization_has_no_preview_or_gcode_vocabulary():
    plan = _plan_with_motions(_quarter_arc(False), _quarter_arc(True))
    hits = probe.serialization_forbidden_hits(plan)
    assert hits == (), hits
    text = probe.candidate_to_json(plan)
    for tok in probe.FORBIDDEN_SERIAL_TOKENS:
        assert tok not in text


def test_plan_does_not_store_preview_or_gcode_types():
    plan = probe.linear_cycle_plan()
    for motion in plan.paths[0].motions:
        assert not isinstance(motion, ToolpathSegment)
        assert type(motion).__name__ in {"LinearMotion", "ArcMotion"}


def test_production_tree_does_not_import_the_probe():
    root = _REPO / "python" / "cam_creation_studio"
    offenders = []
    for path in root.rglob("*.py"):
        if "toolpath_contract_probe" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(_REPO)))
    assert offenders == []
