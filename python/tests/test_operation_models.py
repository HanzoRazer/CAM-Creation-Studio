"""Operation-definition contracts (CS-012).

These pin the dataclasses and closed vocabularies. They do not resolve
intents against a workspace — that is the builder increment.
"""

from __future__ import annotations

import dataclasses

import pytest

from cam_creation_studio.feeds_speeds.calculator import FeedRecommendation
from cam_creation_studio.operations.enums import (
    ContourRelation,
    CutDirection,
    RecommendationStatus,
    SlotRelation,
)
from cam_creation_studio.operations.errors import (
    BindingError,
    OperationDefinitionError,
    RecommendationError,
)
from cam_creation_studio.operations.models import (
    ContourDefinition,
    DrillDefinition,
    EngraveDefinition,
    OperationBinding,
    OperationFeedRecommendation,
    PocketDefinition,
    ReferenceDefinition,
    SlotDefinition,
    definition_type_name,
)

_DEFINITION_CLASSES = (
    ContourDefinition,
    PocketDefinition,
    DrillDefinition,
    EngraveDefinition,
    SlotDefinition,
    ReferenceDefinition,
)

_EXECUTION_FIELDS = (
    "tool",
    "tool_id",
    "material",
    "material_id",
    "feed",
    "feed_rate",
    "rpm",
    "chipload",
    "surface_speed",
    "stepdown",
    "stepover",
    "lead_in",
    "lead_out",
    "tabs",
    "gcode",
    "machine",
    "postprocessor",
    "cutter_diameter",
    "tool_number",
    "z",
)


def test_contour_relation_is_a_closed_str_enum():
    assert {item.value for item in ContourRelation} == {
        "on", "inside", "outside",
    }
    assert ContourRelation.ON == "on"
    assert not hasattr(ContourRelation, "UNSPECIFIED")


def test_cut_direction_is_a_closed_str_enum():
    assert {item.value for item in CutDirection} == {
        "climb", "conventional", "unspecified",
    }
    assert CutDirection.UNSPECIFIED == "unspecified"


def test_slot_relation_is_a_closed_str_enum():
    assert {item.value for item in SlotRelation} == {"on_path"}
    assert SlotRelation.ON_PATH == "on_path"


def test_unknown_vocabulary_fails_clearly():
    with pytest.raises(ValueError):
        ContourRelation("left")
    with pytest.raises(ValueError):
        CutDirection("climb-preferred")
    with pytest.raises(ValueError):
        SlotRelation("centered")


def test_contracts_are_frozen_and_slotted():
    for cls in _DEFINITION_CLASSES:
        assert cls.__dataclass_params__.frozen is True
        assert cls.__dataclass_params__.slots is True


def test_definitions_have_deterministic_equality():
    first = ContourDefinition(
        id="d1", intent_id="op1", target_depth_mm=6.0)
    second = ContourDefinition(
        id="d1", intent_id="op1", target_depth_mm=6.0)
    third = ContourDefinition(
        id="d1", intent_id="op1", target_depth_mm=6.0,
        relation=ContourRelation.OUTSIDE)
    assert first == second
    assert first != third


def test_contour_defaults_are_on_and_unspecified():
    definition = ContourDefinition(
        id="d1", intent_id="op1", target_depth_mm=6.0)
    assert definition.relation is ContourRelation.ON
    assert definition.direction is CutDirection.UNSPECIFIED
    assert definition.stock_allowance_mm is None
    assert definition_type_name(definition) == "contour"


def test_pocket_defaults():
    definition = PocketDefinition(
        id="d1", intent_id="op1", target_depth_mm=4.0)
    assert definition.direction is CutDirection.UNSPECIFIED
    assert definition.wall_allowance_mm is None
    assert definition.floor_allowance_mm is None
    assert definition_type_name(definition) == "pocket"


def test_drill_defaults():
    definition = DrillDefinition(
        id="d1", intent_id="op1", target_depth_mm=10.0)
    assert definition.retract_height_mm is None
    assert definition.peck_depth_mm is None
    assert definition_type_name(definition) == "drill"


def test_engrave_is_identity_intent_and_depth():
    definition = EngraveDefinition(
        id="d1", intent_id="op1", target_depth_mm=0.2)
    names = {field.name for field in dataclasses.fields(definition)}
    assert names == {"id", "intent_id", "target_depth_mm"}
    assert definition_type_name(definition) == "engrave"


def test_slot_defaults_include_on_path_relation():
    definition = SlotDefinition(
        id="d1", intent_id="op1", target_depth_mm=3.0)
    assert definition.relation is SlotRelation.ON_PATH
    assert definition.slot_width_mm is None
    assert definition.direction is CutDirection.UNSPECIFIED
    assert definition_type_name(definition) == "slot"


def test_reference_carries_no_machining_fields():
    definition = ReferenceDefinition(id="d1", intent_id="op1")
    names = {field.name for field in dataclasses.fields(definition)}
    assert names == {"id", "intent_id"}
    assert not hasattr(definition, "target_depth_mm")
    assert definition_type_name(definition) == "reference"


def test_no_definition_exposes_execution_fields():
    for cls in _DEFINITION_CLASSES:
        names = {field.name for field in dataclasses.fields(cls)}
        for forbidden in _EXECUTION_FIELDS:
            assert forbidden not in names


def test_optional_parameters_default_to_none_not_zero():
    contour = ContourDefinition(id="d1", intent_id="op1", target_depth_mm=1.0)
    pocket = PocketDefinition(id="d1", intent_id="op1", target_depth_mm=1.0)
    drill = DrillDefinition(id="d1", intent_id="op1", target_depth_mm=1.0)
    slot = SlotDefinition(id="d1", intent_id="op1", target_depth_mm=1.0)
    assert contour.stock_allowance_mm is None
    assert pocket.wall_allowance_mm is None
    assert pocket.floor_allowance_mm is None
    assert drill.retract_height_mm is None
    assert drill.peck_depth_mm is None
    assert slot.slot_width_mm is None


def test_frozen_instances_reject_assignment():
    definition = EngraveDefinition(
        id="d1", intent_id="op1", target_depth_mm=0.4)
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.target_depth_mm = 1.0  # type: ignore[misc]


def test_operation_definition_error_is_the_structural_exception():
    assert issubclass(OperationDefinitionError, ValueError)
    with pytest.raises(OperationDefinitionError, match="missing intent"):
        raise OperationDefinitionError("missing intent 'op-1'")


def test_operation_binding_is_ids_only():
    binding = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    names = {field.name for field in dataclasses.fields(binding)}
    assert names == {"id", "definition_id", "tool_id", "material_id"}
    assert binding.__dataclass_params__.frozen is True
    assert binding.__dataclass_params__.slots is True


def test_operation_binding_equality_is_deterministic():
    first = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    second = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_4", material_id="hardwood")
    third = OperationBinding(
        id="b1", definition_id="d1",
        tool_id="endmill_1_8", material_id="hardwood")
    assert first == second
    assert first != third


def test_operation_binding_does_not_copy_catalog_fields():
    names = {field.name for field in dataclasses.fields(OperationBinding)}
    for forbidden in (
        "diameter_mm", "flutes", "kind", "label", "notes",
        "chipload_mm", "chipload_mid", "tool", "material",
        "rpm", "feed", "feed_rate", "chipload", "surface_speed",
        "stepdown", "stepover", "machine", "machine_id",
        "postprocessor", "gcode",
    ):
        assert forbidden not in names


def test_binding_error_is_an_operation_definition_error():
    assert issubclass(BindingError, OperationDefinitionError)
    with pytest.raises(BindingError, match="unknown tool"):
        raise BindingError("unknown tool 'missing'")
    with pytest.raises(OperationDefinitionError, match="unknown tool"):
        raise BindingError("unknown tool 'missing'")


def _sample_feed_recommendation() -> FeedRecommendation:
    return FeedRecommendation(
        rpm=12000.0,
        feed_rate=1200.0,
        chipload=0.05,
        surface_speed=239389.0,
    )


def test_recommendation_status_is_a_closed_str_enum():
    assert {item.value for item in RecommendationStatus} == {
        "missing", "current", "stale",
    }
    assert RecommendationStatus.MISSING == "missing"
    assert RecommendationStatus.CURRENT == "current"
    assert RecommendationStatus.STALE == "stale"
    with pytest.raises(ValueError):
        RecommendationStatus("ready")


def test_operation_feed_recommendation_is_attribution_only():
    wrapper = OperationFeedRecommendation(
        id="r1",
        definition_id="d1",
        binding_id="b1",
        machine_profile_id="genericCncRouter",
        spindle_rpm=12000.12345,
        input_fingerprint="fp-1",
        recommendation=_sample_feed_recommendation(),
    )
    names = {field.name for field in dataclasses.fields(wrapper)}
    assert names == {
        "id",
        "definition_id",
        "binding_id",
        "machine_profile_id",
        "spindle_rpm",
        "input_fingerprint",
        "recommendation",
    }
    assert wrapper.__dataclass_params__.frozen is True
    assert wrapper.__dataclass_params__.slots is True
    assert wrapper.spindle_rpm == 12000.12345
    assert isinstance(wrapper.recommendation, FeedRecommendation)


def test_operation_feed_recommendation_equality_is_deterministic():
    payload = _sample_feed_recommendation()
    first = OperationFeedRecommendation(
        id="r1", definition_id="d1", binding_id="b1",
        machine_profile_id="genericCncRouter", spindle_rpm=12000.0,
        input_fingerprint="fp-1", recommendation=payload)
    second = OperationFeedRecommendation(
        id="r1", definition_id="d1", binding_id="b1",
        machine_profile_id="genericCncRouter", spindle_rpm=12000.0,
        input_fingerprint="fp-1", recommendation=payload)
    third = OperationFeedRecommendation(
        id="r1", definition_id="d1", binding_id="b1",
        machine_profile_id="desktop3018", spindle_rpm=12000.0,
        input_fingerprint="fp-2", recommendation=payload)
    assert first == second
    assert first != third


def test_operation_feed_recommendation_does_not_copy_execution_fields():
    names = {field.name for field in dataclasses.fields(OperationFeedRecommendation)}
    for forbidden in (
        "doc_mm", "woc_mm", "stepdown", "stepover", "pass_count",
        "toolpath", "lead_in", "lead_out", "tabs", "compensation",
        "gcode", "postprocessor", "machine_ready", "safe", "approved",
        "diameter_mm", "flutes", "chipload_mm", "max_rpm",
        "tool_id", "material_id",
    ):
        assert forbidden not in names


def test_recommendation_error_is_an_operation_definition_error():
    assert issubclass(RecommendationError, OperationDefinitionError)
    assert not issubclass(RecommendationError, BindingError)
    with pytest.raises(RecommendationError, match="unknown machine"):
        raise RecommendationError("unknown machine 'missing'")
    with pytest.raises(OperationDefinitionError, match="unknown machine"):
        raise RecommendationError("unknown machine 'missing'")
