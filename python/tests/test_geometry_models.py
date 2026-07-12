"""Unit tests for the geometry translation, bounds math, and serialization (CS-008).

These need no ezdxf: the translation layer is duck-typed, so lightweight fake
entities exercise the advisory-diagnostic paths (zero-length line, zero radius,
degenerate polyline, invalid spline) deterministically without fighting ezdxf's
own entity validation.
"""

from __future__ import annotations

import math

import pytest

from cam_creation_studio.geometry import bounds as gbounds
from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.entities import translate
from cam_creation_studio.geometry.models import (
    Arc2D,
    Circle2D,
    GeometryCollection,
    ImportMetadata,
    Line2D,
    Polyline2D,
    Spline2D,
)
from cam_creation_studio.shared.geometry import Bounds, Point
from cam_creation_studio.shared.units import dxf_scale_to_mm, dxf_units_name


# --------------------------------------------------------------------------- #
# Fake ezdxf-like entities (duck typing is all translate() needs)
# --------------------------------------------------------------------------- #
class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeEntity:
    def __init__(self, dxftype, **extra):
        self._t = dxftype
        self.dxf = _NS(**extra.pop("dxf", {}))
        self.__dict__.update(extra)

    def dxftype(self):
        return self._t


def _line(x0, y0, x1, y1, layer="0"):
    return FakeEntity("LINE", dxf={"start": Point(x0, y0), "end": Point(x1, y1),
                                   "layer": layer, "handle": "1A"})


# --------------------------------------------------------------------------- #
# Bounds math
# --------------------------------------------------------------------------- #
def test_arc_extent_includes_top_cardinal():
    # 0->90 arc of r=5 at origin bulges to +Y at 90 deg.
    assert gbounds.arc_extent(0, 0, 5, 0, 90) == pytest.approx((0.0, 0.0, 5.0, 5.0))


def test_arc_extent_full_upper_half_includes_both_x_extremes():
    # 0->180: crosses +Y (90); endpoints at +X and -X.
    assert gbounds.arc_extent(0, 0, 5, 0, 180) == pytest.approx((-5.0, 0.0, 5.0, 5.0))


def test_arc_extent_wrapping_sweep_through_zero():
    # 270->90 wraps through 0 (+X), so +X extreme is included.
    ext = gbounds.arc_extent(0, 0, 2, 270, 90)
    assert ext[2] == pytest.approx(2.0)   # max_x reaches the +X cardinal
    assert ext[1] == pytest.approx(-2.0)  # min_y at the 270 endpoint


def test_union_skips_none_and_combines():
    a = Bounds(0, 0, 1, 1)
    b = Bounds(-1, 2, 0, 3)
    assert gbounds.union([a, None, b]).as_tuple() == (-1.0, 0.0, 1.0, 3.0)


def test_union_all_none_is_none():
    assert gbounds.union([None, None]) is None


def test_arc_extent_zero_sweep_is_the_point():
    # start == end: degenerate arc collapses to its single endpoint.
    assert gbounds.arc_extent(0, 0, 5, 30, 30) == pytest.approx(
        (5 * math.cos(math.radians(30)), 5 * math.sin(math.radians(30)),
         5 * math.cos(math.radians(30)), 5 * math.sin(math.radians(30))))


def test_layers_helpers():
    from cam_creation_studio.geometry import layer_names, on_layer

    col = GeometryCollection(entities=[
        Line2D(Point(0, 0), Point(1, 0), layer="cut"),
        Circle2D(Point(0, 0), 1, layer="holes"),
        Line2D(Point(1, 0), Point(2, 0), layer="cut"),
    ])
    assert layer_names(col) == ["cut", "holes"]
    assert len(on_layer(col, "cut")) == 2


def test_diagnostic_constructors_carry_severity():
    assert diag.info(diag.EMPTY_FILE, "x").severity.value == "info"
    assert diag.danger(diag.INVALID_SPLINE, "x").severity.value == "danger"


def test_bounds_of_empty_points_is_none():
    assert gbounds.bounds_of_points([]) is None


# --------------------------------------------------------------------------- #
# Entity .bounds
# --------------------------------------------------------------------------- #
def test_circle_bounds():
    assert Circle2D(Point(1, 1), 2).bounds.as_tuple() == (-1.0, -1.0, 3.0, 3.0)


def test_line_bounds():
    assert Line2D(Point(0, 0), Point(3, 4)).bounds.as_tuple() == (0.0, 0.0, 3.0, 4.0)


def test_empty_collection_bounds_is_none():
    assert GeometryCollection().bounds is None


# --------------------------------------------------------------------------- #
# Translation advisory diagnostics
# --------------------------------------------------------------------------- #
def test_translate_line_scales_to_mm():
    entity, diags = translate(_line(0, 0, 1, 0), scale=25.4)
    assert isinstance(entity, Line2D)
    assert entity.end.x == pytest.approx(25.4)
    assert diags == []


def test_zero_length_line_warns_but_keeps_geometry():
    entity, diags = translate(_line(2, 2, 2, 2), scale=1.0)
    assert isinstance(entity, Line2D)                       # not discarded
    assert [d.code for d in diags] == [diag.ZERO_LENGTH_LINE]


def test_zero_radius_circle_warns():
    ent = FakeEntity("CIRCLE", dxf={"center": Point(0, 0), "radius": 0.0,
                                    "layer": "0", "handle": "2"})
    entity, diags = translate(ent, scale=1.0)
    assert isinstance(entity, Circle2D)
    assert diag.ZERO_RADIUS in [d.code for d in diags]


def test_degenerate_polyline_warns():
    ent = FakeEntity("LWPOLYLINE", dxf={"layer": "0", "handle": "3"},
                     closed=False, get_points=lambda fmt: [(0, 0)])
    entity, diags = translate(ent, scale=1.0)
    assert isinstance(entity, Polyline2D)
    assert diag.DEGENERATE_POLYLINE in [d.code for d in diags]


def test_invalid_spline_warns_but_keeps_geometry():
    ent = FakeEntity("SPLINE", dxf={"degree": 3, "layer": "0", "handle": "4"},
                     control_points=[Point(0, 0), Point(1, 1)], closed=False)
    entity, diags = translate(ent, scale=1.0)
    assert isinstance(entity, Spline2D)                     # kept, not dropped
    assert diag.INVALID_SPLINE in [d.code for d in diags]


def test_unsupported_entity_returns_none_with_diagnostic():
    entity, diags = translate(FakeEntity("HATCH", dxf={"layer": "0", "handle": "9"}),
                              scale=1.0)
    assert entity is None
    assert [d.code for d in diags] == [diag.UNSUPPORTED_ENTITY]


# --------------------------------------------------------------------------- #
# DXF unit table
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("code,name,scale", [
    (1, "in", 25.4),
    (4, "mm", 1.0),
    (5, "cm", 10.0),
    (6, "m", 1000.0),
])
def test_dxf_unit_table(code, name, scale):
    assert dxf_units_name(code) == name
    assert dxf_scale_to_mm(code) == pytest.approx(scale)


def test_unknown_dxf_units_are_none():
    assert dxf_scale_to_mm(999) is None
    assert dxf_units_name(None) is None


# --------------------------------------------------------------------------- #
# Serialization dispatch edge cases
# --------------------------------------------------------------------------- #
def test_from_dict_unknown_kind_raises():
    with pytest.raises(ValueError):
        GeometryCollection.from_dict({"entities": [{"kind": "nurbs"}]})


def test_round_trip_hand_built_collection():
    col = GeometryCollection(
        entities=[
            Line2D(Point(0, 0), Point(1, 0), layer="a"),
            Arc2D(Point(0, 0), 2, 0, 90, layer="b"),
            Circle2D(Point(5, 5), 1, layer="b"),
            Polyline2D([Point(0, 0), Point(1, 1)], closed=True, layer="a"),
            Spline2D([Point(0, 0), Point(1, 2), Point(2, 0)], degree=2, layer="c"),
        ],
        metadata=ImportMetadata("x.dxf", "mm", 1.0, dxf_version="AC1027", entity_count=5),
        diagnostics=[diag.warning(diag.ZERO_RADIUS, "demo")],
    )
    restored = GeometryCollection.from_json(col.to_json())
    assert [type(e).__name__ for e in restored.entities] == [
        "Line2D", "Arc2D", "Circle2D", "Polyline2D", "Spline2D"]
    assert restored.entities[1].start_angle == 0
    assert restored.entities[3].closed is True
    assert restored.entities[4].degree == 2
    assert restored.metadata.dxf_version == "AC1027"
    assert restored.diagnostics[0].code == diag.ZERO_RADIUS
    assert restored.layers == ["a", "b", "c"]


def test_counts_and_of_kind():
    col = GeometryCollection(entities=[
        Line2D(Point(0, 0), Point(1, 0)),
        Line2D(Point(1, 0), Point(2, 0)),
        Circle2D(Point(0, 0), 1),
    ])
    assert col.counts()["line"] == 2
    assert col.counts()["spline"] == 0
    assert len(col.of_kind("line")) == 2


# --------------------------------------------------------------------------- #
# Importer loop via a fake ezdxf doc (duplicate handles can't be emitted by
# real ezdxf, and this needs no optional dependency).
# --------------------------------------------------------------------------- #
class _FakeHeader(dict):
    pass


class _FakeDoc:
    dxfversion = "AC1027"

    def __init__(self, entities):
        self.header = _FakeHeader({"$INSUNITS": 4})
        self._entities = entities

    def modelspace(self):
        return list(self._entities)


def test_duplicate_handle_is_reported(tmp_path, monkeypatch):
    from cam_creation_studio.geometry import importer as importer_mod

    e1 = _line(0, 0, 1, 0)
    e2 = _line(1, 0, 2, 0)
    e2.dxf.handle = e1.dxf.handle  # force a collision

    class _FakeEzdxf:
        DXFError = Exception

        @staticmethod
        def readfile(path):
            return _FakeDoc([e1, e2])

    monkeypatch.setattr(importer_mod, "_require_ezdxf", lambda: _FakeEzdxf)

    real_file = tmp_path / "dup.dxf"
    real_file.write_text("stub", encoding="utf-8")

    col = importer_mod.import_dxf(str(real_file))
    assert len(col.entities) == 2
    assert diag.DUPLICATE_HANDLE in [d.code for d in col.diagnostics]
