"""End-to-end DXF import tests (CS-008), exercised through real ezdxf docs.

These build DXF documents with ezdxf, save them to a temp path, and import them
back through the public ``import_dxf``. They are skipped automatically if the
optional ``ezdxf`` extra is not installed, honoring the zero-required-dep core.
"""

from __future__ import annotations

import os

import pytest

ezdxf = pytest.importorskip("ezdxf")

from cam_creation_studio.geometry import (  # noqa: E402
    Arc2D,
    Circle2D,
    DxfImportError,
    EzdxfNotInstalled,
    GeometryCollection,
    Line2D,
    Polyline2D,
    import_dxf,
    summarize,
)
from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import importer as importer_mod  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _codes(collection):
    return [d.code for d in collection.diagnostics]


def _save(doc, tmp_path, name="part.dxf"):
    path = os.path.join(str(tmp_path), name)
    doc.saveas(path)
    return path


def _mixed_doc(insunits=4):
    """A doc with one of each supported entity, in a known order."""
    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "cut"})
    msp.add_arc((0, 0), radius=5, start_angle=0, end_angle=90,
                dxfattribs={"layer": "cut"})
    msp.add_circle((20, 20), radius=3, dxfattribs={"layer": "holes"})
    msp.add_lwpolyline([(0, 0), (1, 0), (1, 1)], dxfattribs={"layer": "cut"})
    msp.add_polyline2d([(2, 2), (3, 3)], dxfattribs={"layer": "cut"})
    msp.add_open_spline([(0, 0), (1, 2), (2, 2), (3, 0)],
                        dxfattribs={"layer": "profile"})
    return doc


# --------------------------------------------------------------------------- #
# Happy path: every supported entity type
# --------------------------------------------------------------------------- #
def test_imports_all_supported_entity_kinds(tmp_path):
    col = import_dxf(_save(_mixed_doc(), tmp_path))
    kinds = [e.kind for e in col.entities]
    assert kinds == ["line", "arc", "circle", "polyline", "polyline", "spline"]
    assert isinstance(col.entities[0], Line2D)
    assert isinstance(col.entities[1], Arc2D)
    assert isinstance(col.entities[2], Circle2D)
    assert isinstance(col.entities[3], Polyline2D)


def test_source_order_is_preserved_across_types(tmp_path):
    # Order in the collection must match insertion order, not be grouped by kind.
    col = import_dxf(_save(_mixed_doc(), tmp_path))
    assert [e.kind for e in col.entities][:3] == ["line", "arc", "circle"]


def test_summary_counts(tmp_path):
    s = summarize(import_dxf(_save(_mixed_doc(), tmp_path)))
    assert (s.lines, s.arcs, s.circles, s.polylines, s.splines) == (1, 1, 1, 2, 1)
    assert s.total == 6
    assert set(s.layers) == {"cut", "holes", "profile"}


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #
def test_inches_are_normalized_to_mm(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1  # inches
    doc.modelspace().add_line((0, 0), (1, 0))
    col = import_dxf(_save(doc, tmp_path))
    assert col.metadata.source_units == "in"
    assert col.metadata.unit_scale == pytest.approx(25.4)
    line = col.entities[0]
    assert line.end.x == pytest.approx(25.4)


def test_mm_pass_through_unscaled(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4  # mm
    doc.modelspace().add_line((0, 0), (7, 0))
    col = import_dxf(_save(doc, tmp_path))
    assert col.metadata.unit_scale == 1.0
    assert col.entities[0].end.x == pytest.approx(7.0)


def test_unitless_drawing_warns_and_assumes_mm(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 0  # unitless
    doc.modelspace().add_line((0, 0), (1, 0))
    col = import_dxf(_save(doc, tmp_path))
    assert diag.UNKNOWN_UNITS in _codes(col)
    assert col.metadata.unit_scale == 1.0


# --------------------------------------------------------------------------- #
# Bounds determinism
# --------------------------------------------------------------------------- #
def test_bounds_include_arc_bulge(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    # Quarter arc, radius 5, sweeping through +Y (90 deg) but not +X endpoint only.
    doc.modelspace().add_arc((0, 0), radius=5, start_angle=0, end_angle=90)
    col = import_dxf(_save(doc, tmp_path))
    b = col.bounds
    assert b.as_tuple() == pytest.approx((0.0, 0.0, 5.0, 5.0))


def test_bounds_of_circle(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_circle((10, 10), radius=2)
    col = import_dxf(_save(doc, tmp_path))
    assert col.bounds.as_tuple() == pytest.approx((8.0, 8.0, 12.0, 12.0))


def test_import_is_deterministic(tmp_path):
    path = _save(_mixed_doc(), tmp_path)
    a = import_dxf(path)
    b = import_dxf(path)
    assert a.to_json() == b.to_json()


# --------------------------------------------------------------------------- #
# Serialization round-trip (custom kind-dispatch deserializer)
# --------------------------------------------------------------------------- #
def test_serialization_round_trip(tmp_path):
    col = import_dxf(_save(_mixed_doc(insunits=1), tmp_path))
    restored = GeometryCollection.from_json(col.to_json())
    assert [e.kind for e in restored.entities] == [e.kind for e in col.entities]
    assert restored.bounds.as_tuple() == pytest.approx(col.bounds.as_tuple())
    assert restored.metadata.source_units == col.metadata.source_units
    assert restored.metadata.unit_scale == col.metadata.unit_scale
    assert _codes(restored) == _codes(col)


# --------------------------------------------------------------------------- #
# Layer metadata preserved
# --------------------------------------------------------------------------- #
def test_layer_names_preserved(tmp_path):
    from cam_creation_studio.geometry import by_layer

    col = import_dxf(_save(_mixed_doc(), tmp_path))
    grouped = by_layer(col)
    assert set(grouped) == {"cut", "holes", "profile"}
    assert all(e.layer == "holes" for e in grouped["holes"])


# --------------------------------------------------------------------------- #
# Boundary & negative cases
# --------------------------------------------------------------------------- #
def test_empty_modelspace_reports_empty_file(tmp_path):
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    col = import_dxf(_save(doc, tmp_path))
    assert col.entities == []
    assert diag.EMPTY_FILE in _codes(col)


def test_unsupported_entity_is_reported_not_dropped_silently(tmp_path):
    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_line((0, 0), (1, 0))
    msp.add_text("hello").set_placement((0, 0))  # TEXT: unsupported
    col = import_dxf(_save(doc, tmp_path))
    assert len(col.entities) == 1                 # only the line survives as geometry
    assert diag.UNSUPPORTED_ENTITY in _codes(col)  # but TEXT is not silent


def test_missing_file_raises(tmp_path):
    with pytest.raises(DxfImportError):
        import_dxf(os.path.join(str(tmp_path), "nope.dxf"))


def test_corrupt_dxf_raises(tmp_path):
    path = os.path.join(str(tmp_path), "corrupt.dxf")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("this is not a dxf file\n0\nGARBAGE\n")
    with pytest.raises(DxfImportError):
        import_dxf(path)


def test_ezdxf_absent_raises_actionable_error(tmp_path, monkeypatch):
    # A real file so the isfile() gate passes; the dependency guard fires next.
    path = _save(_mixed_doc(), tmp_path)

    def _boom():
        raise EzdxfNotInstalled(importer_mod._INSTALL_HINT)

    monkeypatch.setattr(importer_mod, "_require_ezdxf", _boom)
    with pytest.raises(EzdxfNotInstalled) as exc:
        import_dxf(path)
    assert "cam-creation-studio[dxf]" in str(exc.value)
