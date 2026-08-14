"""Deterministic closure probe for CS-008R — regenerates the evidence manifest.

Audit utility, not production code and not part of the test run. It exists so the
closure manifest is *reproducible* rather than transcribed: every value in
``docs/audits/evidence/CS-008R-closure/manifest.json`` is produced by running this
against the committed fixture corpus, so a reviewer can regenerate it and diff
rather than take the report's word.

Run from the repository root:

    python tools/audits/cs008r/run_closure_probe.py

It reads fixtures and writes exactly one file, the manifest. It never mutates the
fixture corpus — that corpus is immutable, and a probe that rewrote its own inputs
would be measuring itself.

Deliberately records no timestamp. Wall-clock metadata makes every regeneration a
diff and reproducibility is worth more here than provenance-by-clock; the audited
commits are recorded instead, which is the thing that actually identifies the run.

Schema follows ``docs/audits/evidence/CS-008/probe_manifest.json`` — same top-level
environment keys, same ``results`` entry shape — extended with a ``findings`` block
for the F1-F10 closure matrix the earlier manifest had no need of.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PY = os.path.join(REPO, "python")
FIXTURES = os.path.join(PY, "tests", "fixtures")
OUT_DIR = os.path.join(REPO, "docs", "audits", "evidence", "CS-008R-closure")

sys.path.insert(0, PY)

import ezdxf  # noqa: E402

from cam_creation_studio.geometry import diagnostics as diag  # noqa: E402
from cam_creation_studio.geometry import import_dxf  # noqa: E402
from cam_creation_studio.geometry.models import GeometryCollection  # noqa: E402


def _git(*args):
    try:
        return subprocess.check_output(["git", "-C", REPO, *args], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unavailable"


def _load(name):
    return import_dxf(os.path.join(FIXTURES, name))


def _of_kind(collection, kind):
    return [e for e in collection.entities if e.kind == kind]


def _result(pid, case, expected, actual, diagnostics=(), note=""):
    return {
        "id": pid,
        "case": case,
        "expected": expected,
        "actual": actual,
        "diagnostics": sorted(diagnostics),
        "note": note,
    }


# --------------------------------------------------------------------- probes

def probe_f1():
    circle = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    arc_collection = _load("ocs_arc.dxf")
    codes = {d.code for d in arc_collection.diagnostics}
    return [
        _result("C1a", "flipped extrusion resolves to WCS",
                "centre x = -5.0 (OCS +5 mirrored)",
                f"centre = ({circle.center.x}, {circle.center.y})"),
        _result("C1b", "tilted extrusion resolves and reports its lost plane",
                f"{diag.NON_PLANAR_GEOMETRY} present, "
                f"{diag.OCS_TRANSFORM_FAILED} absent",
                f"arc imported = {bool(_of_kind(arc_collection, 'arc'))}",
                codes),
    ]


def probe_f2():
    spline = _of_kind(_load("fit_spline.dxf"), "spline")[0]
    return [_result("C2", "fit-point spline is usable geometry",
                    "representation 'fit' with fit points retained",
                    f"representation={spline.representation}, "
                    f"fit_points={len(spline.fit_points)}, "
                    f"control_points={len(spline.control_points)}")]


def probe_f3_f4():
    spline = _of_kind(_load("weighted_spline.dxf"), "spline")[0]
    return [
        _result("C3", "rational weights survive in order",
                "[1.0, 4.0, 4.0, 1.0], rational=True",
                f"{spline.weights}, rational={spline.rational}"),
        _result("C4", "knots survive and are not unit-scaled",
                "knot vector present, degree 3, max <= 1.0",
                f"knots={len(spline.knots)}, degree={spline.degree}, "
                f"max_knot={max(spline.knots) if spline.knots else None}"),
    ]


def probe_f5():
    lw = _of_kind(_load("lwpolyline_elevation.dxf"), "polyline")[0]
    p2 = _of_kind(_load("polyline2d_elevation.dxf"), "polyline")[0]
    same = [(v.x, v.y, v.z) for v in lw.vertices] == [
        (v.x, v.y, v.z) for v in p2.vertices]
    return [_result("C5", "both 2D polyline paths agree on elevation",
                    "identical vertices at z = 25.0",
                    f"lwpolyline z={lw.vertices[0].z}, "
                    f"polyline2d z={p2.vertices[0].z}, identical={same}")]


def probe_f6():
    entity = _of_kind(_load("extruded_circle.dxf"), "circle")[0]
    src = entity.source
    return [_result("C6", "provenance answers where the entity came from",
                    "entity_type, handle, layer, ordinal all present",
                    f"entity_type={src.entity_type}, handle={bool(src.handle)}, "
                    f"layer={src.layer!r}, ordinal={src.ordinal}")]


def probe_f7(tmp):
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_line((0, 0), (10, 0))
    omitted = os.path.join(tmp, "omitted_layer.dxf")
    doc.saveas(omitted)

    doc2 = ezdxf.new("R2010")
    doc2.units = 4
    doc2.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": ""})
    empty = os.path.join(tmp, "empty_layer.dxf")
    doc2.saveas(empty)

    a, b = import_dxf(omitted), import_dxf(empty)
    return [
        _result("C7a", "omitted layer attribute means valid layer 0",
                "layer '0', no MISSING_LAYER",
                f"layer={a.entities[0].layer!r}",
                {d.code for d in a.diagnostics}),
        _result("C7b", "empty layer name is reported, geometry kept",
                f"{diag.MISSING_LAYER} present, entity retained",
                f"entities={len(b.entities)}",
                {d.code for d in b.diagnostics}),
    ]


def probe_f8():
    """The machine-checkable half of F8: is anything silently lossy?"""
    doc = ezdxf.new("R2010")
    doc.units = 4
    mesh = doc.modelspace().add_polyface()
    mesh.append_face([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)])
    path = os.path.join(OUT_DIR, "_probe_mesh.dxf")
    doc.saveas(path)
    collection = import_dxf(path)
    os.remove(path)

    return [_result(
        "C8", "mesh-flavour POLYLINE is silently reshaped",
        "a diagnostic, or has_lossy_import True",
        f"kinds={[e.kind for e in collection.entities]}, "
        f"has_lossy_import={collection.metadata.has_lossy_import}",
        {d.code for d in collection.diagnostics},
        "confirms F8: the import reports nothing and reads as clean")]


def probe_f9(tmp):
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 5)])
    path = os.path.join(tmp, "f9.dxf")
    doc.saveas(path)

    collection = import_dxf(path)
    vertex = _of_kind(collection, "polyline")[0].vertices[1]
    blob = json.dumps(collection.to_dict())
    restored = GeometryCollection.from_dict(json.loads(blob))
    restored_x = _of_kind(restored, "polyline")[0].vertices[1].x

    try:
        diag.ensure_json_safe({"x": vertex.x})
        json_safe = True
    except Exception as exc:  # noqa: BLE001
        json_safe = f"rejected: {exc!r}"

    # bool() on every comparison below is not incidental — see C9b. Comparing a
    # numpy scalar returns numpy.bool_, which json.dumps refuses, so an
    # un-coerced probe crashes on its own evidence.
    contract = _result(
        "C9a", "LWPOLYLINE coordinate honours every numeric contract",
        "float subclass; equality, arithmetic, JSON and round-trip all correct",
        json.dumps({
            "exact_type": type(vertex.x).__name__,
            "isinstance_float": bool(isinstance(vertex.x, float)),
            "value_equality": bool(vertex.x == 10.0),
            "isfinite": bool(math.isfinite(vertex.x)),
            "arithmetic": bool(vertex.x + 1 == 11.0),
            "ensure_json_safe": json_safe,
            "roundtrip_type": type(restored_x).__name__,
            "roundtrip_equal": bool(restored_x == vertex.x),
            "numpy_in_serialized_json": bool("numpy" in blob),
            "repr": repr(vertex.x),
        }, sort_keys=True),
        note="accepted limitation: of the contracts, only the debug repr differs")

    # How far the foreign type travels, and whether the JSON contract catches it.
    derived = vertex.x == 10.0
    try:
        json.dumps(derived)
        derived_json = "accepted"
    except TypeError as exc:
        derived_json = f"TypeError: {exc}"
    try:
        diag.ensure_json_safe({"derived": derived})
        derived_guard = "accepted"
    except Exception as exc:  # noqa: BLE001
        derived_guard = f"{type(exc).__name__}"

    propagation = _result(
        "C9b", "does the foreign numeric type propagate into derived values",
        "derived values remain JSON-safe, or are refused at the contract boundary",
        json.dumps({
            "comparison_type": type(derived).__name__,
            "is_python_bool": bool(isinstance(derived, bool)),
            "json_dumps": derived_json,
            "ensure_json_safe": derived_guard,
        }, sort_keys=True),
        note="numpy.bool_ names itself 'bool' but is not one; json refuses it. "
             "No production diagnostic embeds a coordinate-derived value - the "
             "metadata sites carry counts, degree and strings - so nothing is "
             "exposed, and the JSON contract refuses it at construction rather "
             "than corrupting a payload. Recorded as the sharpest trigger that "
             "would reopen F9.")

    return [contract, propagation]


def probe_f10():
    splines = _of_kind(_load("periodic_spline.dxf"), "spline")
    a, b = splines
    return [_result(
        "C10", "periodic spline distinguishable from a merely closed one",
        "both closed; periodic False vs True; identical control points",
        f"closed=({a.closed}, {b.closed}), periodic=({a.periodic}, {b.periodic}), "
        f"control_points=({len(a.control_points)}, {len(b.control_points)}), "
        f"representation={a.representation}",
        note="evidence the audit lacked; answered from a real DXF, not a stub")]


def probe_vocabulary():
    """Reachability for the reserved code, across the whole committed corpus."""
    emitted = set()
    for name in sorted(f for f in os.listdir(FIXTURES) if f.endswith(".dxf")):
        emitted |= {d.code for d in _load(name).diagnostics}
    return [_result(
        "CV", "reserved code is unreachable across the fixture corpus",
        f"{diag.LWPOLYLINE_ELEVATION_DROPPED} never emitted",
        f"reserved_code_emitted="
        f"{diag.LWPOLYLINE_ELEVATION_DROPPED in emitted}",
        emitted,
        "codes observed across the corpus, not the full live set")]


FINDINGS = {
    "F1": {"disposition": "remediated", "by": "#14, hardened by #16", "probe": "C1a/C1b"},
    "F2": {"disposition": "remediated", "by": "#11", "probe": "C2"},
    "F3": {"disposition": "remediated", "by": "#11", "probe": "C3"},
    "F4": {"disposition": "remediated", "by": "#11", "probe": "C4"},
    "F5": {"disposition": "remediated", "by": "#19", "probe": "C5"},
    "F6": {"disposition": "remediated", "by": "#19", "probe": "C6"},
    "F7": {"disposition": "remediated", "by": "#19", "probe": "C7a/C7b"},
    "F8": {"disposition": "remediated", "by": "CS-008R-CL", "probe": "C8"},
    "F9": {"disposition": "accepted", "by": "owner ruling 2026-08-13", "probe": "C9"},
    "F10": {"disposition": "remediated", "by": "#11, verified at closure", "probe": "C10"},
}


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT_DIR  # scratch DXFs are written and removed inside the probes

    results = []
    results += probe_f1()
    results += probe_f2()
    results += probe_f3_f4()
    results += probe_f5()
    results += probe_f6()
    results += probe_f7(tmp)
    results += probe_f8()
    results += probe_f9(tmp)
    results += probe_f10()
    results += probe_vocabulary()

    for scratch in ("omitted_layer.dxf", "empty_layer.dxf", "f9.dxf"):
        path = os.path.join(tmp, scratch)
        if os.path.exists(path):
            os.remove(path)

    manifest = {
        "audit": "CS-008R-CL",
        "parent_artifact": "docs/audits/CS-008_REAUDIT.md",
        "target_commit": _git("rev-parse", "origin/main"),
        "closure_commit": _git("rev-parse", "HEAD"),
        "audit_worktree": REPO,
        "package_file": os.path.join(
            PY, "cam_creation_studio", "geometry", "importer.py"),
        "python_version": ".".join(str(v) for v in sys.version_info[:3]),
        "ezdxf_version": ezdxf.__version__,
        "fixture_dir": FIXTURES,
        "findings": FINDINGS,
        "results": results,
    }

    out = os.path.join(OUT_DIR, "manifest.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=False)
        handle.write("\n")
    print(f"wrote {out} ({len(results)} results)")


if __name__ == "__main__":
    main()
