import math

import pytest

from cam_creation_studio.shared.ids import new_id, stable_id
from cam_creation_studio.shared.numbers import (
    clamp,
    clamp_number,
    lerp,
    normalize_angle,
    round_gcode,
    round_for_gcode,
)
from cam_creation_studio.shared.serialization import from_dict, to_dict


# ---- math utilities (mathutils responsibility lives in numbers) ----
def test_lerp():
    assert lerp(0, 10, 0.5) == 5
    assert lerp(0, 10, 0) == 0
    assert lerp(0, 10, 1) == 10
    assert lerp(10, 20, -1) == 0  # extrapolates


def test_normalize_angle_wraps_into_pi_range():
    assert normalize_angle(0) == 0
    assert normalize_angle(3 * math.pi) == pytest.approx(-math.pi)
    assert -math.pi <= normalize_angle(100) < math.pi


def test_aliases_point_at_canonical():
    assert clamp is clamp_number
    assert round_gcode is round_for_gcode
    assert clamp(5, 0, 3) == 3
    assert round_gcode(10.0) == 10


# ---- serialization on nested/enum structures ----
def test_to_dict_handles_enum_and_nested():
    from cam_creation_studio.models import Move, Point
    from cam_creation_studio.enums import MoveType

    assert to_dict(MoveType.LINEAR) == "G1"
    assert to_dict([Point(1, 2), Point(3, 4)]) == [
        {"x": 1, "y": 2, "z": 0.0}, {"x": 3, "y": 4, "z": 0.0}
    ]
    d = to_dict(Move(x=1, y=2, feed=100))
    assert d["type"] == "G1" and d["x"] == 1


def test_from_dict_requires_dataclass():
    with pytest.raises(TypeError):
        from_dict(int, {})


# ---- ids ----
def test_stable_id_is_deterministic():
    assert stable_id("a", "b") == stable_id("a", "b")
    assert stable_id("a", "b") != stable_id("a", "c")
    assert stable_id("x", prefix="job-").startswith("job-")


def test_new_id_is_unique_and_prefixed():
    assert new_id() != new_id()
    assert new_id("move-").startswith("move-")
