"""Missing-layer evidence semantics (CS-008R F7).

``MISSING_LAYER`` was declared but never emitted. The reason was upstream of the
diagnostic: :func:`_layer_of` coerced an absent *or* empty layer to ``"0"``, so
by the time anything could have judged the evidence, the difference between
"omitted" and "named nothing" had already been normalized away.

The semantics, decided before implementation:

===============================  ==========================  ==================
source condition                 meaning                     finding
===============================  ==========================  ==================
layer attribute absent           the entity is on layer 0    none
``layer = "0"``                  a real, ordinary layer      none
``layer = ""``                   names nothing               ``MISSING_LAYER``
name absent from layer table     resolves to nothing         ``MISSING_LAYER``
===============================  ==========================  ==================

The first row matters most: in DXF an omitted layer group code *means* layer
``"0"``. Flagging it would fire on ordinary, valid files — a false positive
dressed as rigour. So the diagnostic is reserved for evidence that is genuinely
unsound, not merely terse.

Layer evidence never withholds geometry: a layer finding rides alongside the
imported entity, it does not replace it.

Audited defect: CS-008R F7, docs/audits/CS-008_REAUDIT.md.
"""

from __future__ import annotations

import pytest

ezdxf = pytest.importorskip("ezdxf")

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry.entities import (  # noqa: E402
    LAYER_EMPTY,
    LAYER_UNKNOWN_REFERENCE,
    LAYER_VALID,
    layer_condition,
    translate,
)


def _import(populate, tmp_path, name="layers.dxf"):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    populate(doc)
    path = str(tmp_path / name)
    doc.saveas(path)
    return import_dxf(path)


def _codes(collection):
    return [d.code for d in collection.diagnostics]


class _Stub:
    """Minimal entity for classifying layer evidence without a document."""

    def __init__(self, **dxf):
        self.dxf = type("_NS", (), dxf)()

    def dxftype(self):
        return "LINE"


# --------------------------------------------------------------------------- #
# Classification, isolated from file parsing
# --------------------------------------------------------------------------- #
def test_absent_layer_attribute_is_valid_layer_zero():
    """The decisive case: omission *means* layer 0, so it is not a finding."""
    assert layer_condition(_Stub()) == LAYER_VALID


def test_layer_zero_is_valid():
    assert layer_condition(_Stub(layer="0"), frozenset({"0"})) == LAYER_VALID


def test_ordinary_named_layer_is_valid():
    assert layer_condition(_Stub(layer="PROFILE"),
                           frozenset({"0", "PROFILE"})) == LAYER_VALID


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_layer_name_is_a_finding(value):
    assert layer_condition(_Stub(layer=value)) == LAYER_EMPTY


def test_name_absent_from_the_table_is_a_finding():
    assert layer_condition(_Stub(layer="GHOST"),
                           frozenset({"0"})) == LAYER_UNKNOWN_REFERENCE


def test_unknown_reference_is_skipped_without_a_layer_table():
    """No table means the check cannot be made — skipped, never guessed."""
    assert layer_condition(_Stub(layer="GHOST")) == LAYER_VALID


# --------------------------------------------------------------------------- #
# Through a real file
# --------------------------------------------------------------------------- #
def test_valid_layers_produce_no_finding(tmp_path):
    def build(doc):
        doc.layers.add("PROFILE")
        doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "PROFILE"})

    assert diag.MISSING_LAYER not in _codes(_import(build, tmp_path))


def test_layer_zero_is_never_flagged(tmp_path):
    """Explicitly pinned: the most common layer in any DXF must stay silent."""
    collection = _import(lambda d: d.modelspace().add_line((0, 0), (10, 0)),
                         tmp_path)
    assert collection.entities[0].layer == "0"
    assert diag.MISSING_LAYER not in _codes(collection)


def test_empty_layer_name_is_reported(tmp_path):
    collection = _import(
        lambda d: d.modelspace().add_line((0, 0), (10, 0),
                                          dxfattribs={"layer": ""}), tmp_path)
    assert diag.MISSING_LAYER in _codes(collection)


def test_unknown_layer_reference_is_reported(tmp_path):
    collection = _import(
        lambda d: d.modelspace().add_line((0, 0), (10, 0),
                                          dxfattribs={"layer": "GHOST"}), tmp_path)
    assert diag.MISSING_LAYER in _codes(collection)
    finding = [d for d in collection.diagnostics
               if d.code == diag.MISSING_LAYER][0]
    assert "GHOST" in finding.message


# --------------------------------------------------------------------------- #
# Evidence, not rejection
# --------------------------------------------------------------------------- #
def test_geometry_still_imports_despite_a_layer_finding(tmp_path):
    collection = _import(
        lambda d: d.modelspace().add_line((0, 0), (10, 0),
                                          dxfattribs={"layer": "GHOST"}), tmp_path)
    assert len(collection.entities) == 1
    assert collection.entities[0].end.x == 10.0


def test_exactly_one_finding_per_affected_entity(tmp_path):
    def build(doc):
        msp = doc.modelspace()
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "GHOST"})
        msp.add_circle((0, 0), radius=5, dxfattribs={"layer": ""})
        msp.add_line((0, 5), (10, 5))                       # valid, layer 0

    collection = _import(build, tmp_path)
    assert _codes(collection).count(diag.MISSING_LAYER) == 2


def test_the_finding_locates_the_entity(tmp_path):
    collection = _import(
        lambda d: d.modelspace().add_circle((0, 0), radius=5,
                                            dxfattribs={"layer": "GHOST"}),
        tmp_path)
    finding = [d for d in collection.diagnostics
               if d.code == diag.MISSING_LAYER][0]
    assert finding.entity_type == "CIRCLE"
    assert finding.handle


def test_an_unsupported_entity_still_reports_its_layer_evidence(tmp_path):
    """A dropped entity's layer is still a fact about the source."""
    collection = _import(
        lambda d: d.modelspace().add_text("x", dxfattribs={"layer": "GHOST"}),
        tmp_path)
    assert diag.UNSUPPORTED_ENTITY in _codes(collection)
    assert diag.MISSING_LAYER in _codes(collection)


def test_layer_evidence_survives_serialization(tmp_path):
    from cam_creation_studio.geometry.models import GeometryCollection
    collection = _import(
        lambda d: d.modelspace().add_line((0, 0), (10, 0),
                                          dxfattribs={"layer": "GHOST"}), tmp_path)
    restored = GeometryCollection.from_dict(collection.to_dict())
    assert diag.MISSING_LAYER in [d.code for d in restored.diagnostics]


def test_layer_findings_are_deterministic(tmp_path):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "GHOST"})
    path = str(tmp_path / "det.dxf")
    doc.saveas(path)
    assert import_dxf(path).to_dict() == import_dxf(path).to_dict()


def test_translation_without_a_layer_table_stays_silent():
    """Duck-typed translation has no document, so the table check is skipped."""
    _, diags = translate(
        type("S", (), {"dxf": type("D", (), {"start": (0, 0, 0), "end": (1, 0, 0),
                                             "layer": "GHOST"})(),
                       "dxftype": lambda self: "LINE"})(), 1.0)
    assert diag.MISSING_LAYER not in [d.code for d in diags]
