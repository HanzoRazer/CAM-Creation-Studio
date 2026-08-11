"""Source provenance for imported geometry (CS-008R F6).

An imported entity must be able to answer *where did I come from* — DXF type,
handle, layer, and position in the source modelspace. That is evidence about the
file, not interpretation of it, so it lives on the entity rather than in a
diagnostic, and successful preservation is silent.

Two decisions here are deliberate and are pinned below rather than left to be
rediscovered:

* ``source`` is excluded from equality. Geometry equality stays *geometric*: two
  identical shapes compare equal whether or not they share a handle.
* ``ordinal`` is the **modelspace** position, not the index within
  ``GeometryCollection.entities``. When an entity is dropped, the imported
  sequence keeps the gap, and the gap is itself evidence that something did not
  survive. Collection position is already available from list order.

Audited defect: CS-008R F6, docs/audits/CS-008_REAUDIT.md.
"""

from __future__ import annotations

import pytest

ezdxf = pytest.importorskip("ezdxf")

from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry.entities import translate  # noqa: E402
from cam_creation_studio.geometry.models import (  # noqa: E402
    GeometryCollection,
    Line2D,
    SourceReference,
)
from cam_creation_studio.shared.geometry import Point  # noqa: E402


def _import(populate, tmp_path, name="prov.dxf"):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    populate(doc.modelspace())
    path = str(tmp_path / name)
    doc.saveas(path)
    return import_dxf(path)


def _all_kinds(msp):
    msp.add_line((0, 0), (10, 0))
    msp.add_arc((0, 0), radius=5, start_angle=0, end_angle=90)
    msp.add_circle((0, 0), radius=5)
    msp.add_lwpolyline([(0, 0), (10, 0)])
    msp.add_polyline2d([(0, 0), (10, 0)])
    msp.add_spline(fit_points=[(0, 0), (5, 8), (10, 0)])


# --------------------------------------------------------------------------- #
# Every supported entity carries provenance
# --------------------------------------------------------------------------- #
def test_every_supported_entity_kind_carries_a_source_reference(tmp_path):
    collection = _import(_all_kinds, tmp_path)
    assert len(collection.entities) == 6
    for entity in collection.entities:
        assert entity.source is not None, f"{entity.kind} has no provenance"
        assert entity.source.handle, f"{entity.kind} has no handle"


@pytest.mark.parametrize("dxftype,kind", [
    ("LINE", "line"), ("ARC", "arc"), ("CIRCLE", "circle"),
    ("LWPOLYLINE", "polyline"), ("POLYLINE", "polyline"), ("SPLINE", "spline"),
])
def test_source_records_the_dxf_type_not_the_model_kind(dxftype, kind, tmp_path):
    """LWPOLYLINE and POLYLINE both become `polyline`; provenance keeps them apart."""
    collection = _import(_all_kinds, tmp_path)
    matching = [e for e in collection.entities if e.source.entity_type == dxftype]
    assert matching, f"no entity recorded source type {dxftype}"
    assert all(e.kind == kind for e in matching)


def test_source_records_the_layer(tmp_path):
    def build(msp):
        msp.doc.layers.add("PROFILE")
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "PROFILE"})

    entity = _import(build, tmp_path).entities[0]
    assert entity.source.layer == "PROFILE"
    assert entity.layer == "PROFILE", "the geometry's own layer is unaffected"


def test_handle_is_none_when_the_source_has_none():
    """A duck-typed entity outside an import has no handle; None, not invented."""
    class NoHandle:
        class dxf:
            start = (0.0, 0.0, 0.0)
            end = (10.0, 0.0, 0.0)
            layer = "0"

        def dxftype(self):
            return "LINE"

    model, _ = translate(NoHandle(), 1.0)
    assert model.source.handle is None
    assert model.source.entity_type == "LINE"
    assert model.source.ordinal is None, "no modelspace position outside an import"


# --------------------------------------------------------------------------- #
# Ordinal is the modelspace position, and gaps are the point
# --------------------------------------------------------------------------- #
def test_ordinal_follows_source_order(tmp_path):
    collection = _import(_all_kinds, tmp_path)
    assert [e.source.ordinal for e in collection.entities] == [0, 1, 2, 3, 4, 5]


def test_a_dropped_entity_leaves_a_gap_in_the_ordinals(tmp_path):
    """The gap records that modelspace entity 1 did not survive the import.

    A dense index over imported entities could not express this — it would
    renumber the survivors and erase the evidence that anything was lost.
    """
    def build(msp):
        msp.add_line((0, 0), (10, 0))
        msp.add_text("unsupported")          # dropped as UNSUPPORTED_ENTITY
        msp.add_circle((0, 0), radius=5)

    collection = _import(build, tmp_path)
    assert len(collection.entities) == 2
    assert [e.source.ordinal for e in collection.entities] == [0, 2]
    assert collection.metadata.unsupported_entity_count == 1


def test_ordinal_is_not_the_collection_index(tmp_path):
    def build(msp):
        msp.add_text("dropped")
        msp.add_line((0, 0), (10, 0))

    collection = _import(build, tmp_path)
    assert collection.entities[0].source.ordinal == 1, "modelspace position"


# --------------------------------------------------------------------------- #
# Provenance does not redefine geometry
# --------------------------------------------------------------------------- #
def test_identical_shapes_from_different_handles_compare_equal():
    """`compare=False`: geometry equality stays geometric."""
    shape = dict(start=Point(0, 0), end=Point(10, 0))
    a = Line2D(**shape, source=SourceReference("LINE", handle="A", ordinal=0))
    b = Line2D(**shape, source=SourceReference("LINE", handle="B", ordinal=7))
    assert a == b
    assert a.source != b.source, "the provenance itself still differs"


def test_geometry_without_provenance_equals_the_same_geometry_with_it():
    shape = dict(start=Point(0, 0), end=Point(10, 0))
    assert Line2D(**shape) == Line2D(**shape,
                                     source=SourceReference("LINE", handle="A"))


def test_differing_geometry_is_still_unequal():
    """Guard the obvious: compare=False must not make everything equal."""
    assert Line2D(start=Point(0, 0), end=Point(10, 0)) != \
           Line2D(start=Point(0, 0), end=Point(11, 0))


def test_successful_provenance_is_silent(tmp_path):
    collection = _import(_all_kinds, tmp_path)
    assert [d.code for d in collection.diagnostics] == []


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def test_provenance_round_trips(tmp_path):
    collection = _import(_all_kinds, tmp_path)
    restored = GeometryCollection.from_dict(collection.to_dict())
    for before, after in zip(collection.entities, restored.entities):
        assert after.source == before.source


def test_provenance_appears_in_the_serialized_payload(tmp_path):
    entity = _import(lambda m: m.add_line((0, 0), (10, 0)), tmp_path).entities[0]
    payload = GeometryCollection(entities=[entity]).to_dict()["entities"][0]
    assert set(payload["source"]) == {"entity_type", "handle", "layer", "ordinal"}
    assert payload["source"]["entity_type"] == "LINE"


def test_geometry_serialized_before_provenance_still_loads():
    """Backward compatibility: `source` is additive and defaults to None."""
    legacy = {"kind": "line",
              "start": {"x": 0.0, "y": 0.0, "z": 0.0},
              "end": {"x": 10.0, "y": 0.0, "z": 0.0},
              "layer": "0"}
    restored = GeometryCollection.from_dict(
        {"entities": [legacy], "metadata": None, "diagnostics": []})
    assert restored.entities[0].source is None
    assert restored.entities[0].end.x == 10.0


def test_import_with_provenance_is_deterministic(tmp_path):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    _all_kinds(doc.modelspace())
    path = str(tmp_path / "det.dxf")
    doc.saveas(path)
    assert import_dxf(path).to_dict() == import_dxf(path).to_dict()


def test_duplicate_handles_are_still_reported(tmp_path):
    """Provenance must not displace the existing duplicate-handle diagnostic."""
    from cam_creation_studio.geometry import diagnostics as diag

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    first = msp.add_line((0, 0), (10, 0))
    second = msp.add_line((0, 5), (10, 5))
    second.dxf.handle = first.dxf.handle
    path = str(tmp_path / "dupe.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    assert diag.DUPLICATE_HANDLE in [d.code for d in collection.diagnostics]
