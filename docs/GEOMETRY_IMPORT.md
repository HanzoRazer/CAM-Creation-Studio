# Geometry Import (DXF → Neutral Geometry Model)

The `geometry` subsystem ingests 2D DXF geometry into a machine-independent
domain model. It answers **"what geometry exists"** — never **"how it will be
machined."** There is no toolpath, feeds/speeds, offsetting, or G-code logic
here, by constitutional boundary. Interpretation happens in later subsystems.

```text
DXF File  ─▶  import_dxf()  ─▶  GeometryCollection  ─▶  (future operations)
```

## Public API

```python
from cam_creation_studio.geometry import import_dxf, summarize, GeometryCollection

collection = import_dxf("part.dxf")
```

- **`import_dxf(path) -> GeometryCollection`** — the single entry point. Reads the
  file, normalizes units to millimetres, translates every supported entity in
  source order, and attaches advisory diagnostics.
- **`GeometryCollection`** — an ordered, heterogeneous list of entities plus
  `metadata` (`ImportMetadata`) and `diagnostics` (`list[GeometryDiagnostic]`).
  Derived views: `.bounds`, `.layers`, `.counts()`, `.of_kind(kind)`.
- **`summarize(collection) -> GeometrySummary`** — deterministic counts, bounds,
  and layer list for inspection.
- **`layer_names` / `by_layer` / `on_layer`** — group entities by source layer.

### Entities

All are immutable dataclasses that reuse the canonical
`shared.geometry.Point` / `Bounds` primitives (no parallel `Point2D` type). Each
carries a `kind` discriminator and its source `layer`.

| Class | `kind` | Key fields |
|-------|--------|-----------|
| `Line2D` | `"line"` | `start`, `end` |
| `Arc2D` | `"arc"` | `center`, `radius`, `start_angle`, `end_angle` (deg, CCW) |
| `Circle2D` | `"circle"` | `center`, `radius` |
| `Polyline2D` | `"polyline"` | `vertices`, `closed` |
| `Spline2D` | `"spline"` | `control_points`, `degree`, `closed` |

DXF `LINE`, `ARC`, `CIRCLE`, `LWPOLYLINE`, `POLYLINE`, and `SPLINE` are supported.
Any other entity type produces an `UNSUPPORTED_ENTITY` diagnostic and is **not**
represented as geometry — but it is never dropped silently.

### What is *not* preserved yet (fidelity limits)

A **successful import is not a guarantee of full geometric fidelity.** These are
surfaced as diagnostics (or an unsupported-entity drop), never silent — but a
consumer that needs faithful geometry must check them:

| Source construct | Behavior | Signal |
|------------------|----------|--------|
| Polyline **bulges** (arc segments) | Flattened to straight chords; vertices kept | `POLYLINE_BULGE_IGNORED` |
| **SPLINE** knot vectors, weights, fit points | Dropped; only control points + degree kept | ⚠ **none — silent** |
| **OCS / extrusion vectors** | **Not applied.** Entities import at raw OCS coordinates | ⚠ **none — silent** |
| **LWPOLYLINE** `elevation` | **Dropped.** Z flattened to 0 (POLYLINE keeps Z) | ⚠ **none — silent** |
| **ELLIPSE**, **TEXT**, **MTEXT**, **HATCH**, **DIMENSION** | Not represented | `UNSUPPORTED_ENTITY` |
| **INSERT** / block references | Not expanded; block contents do not appear | `UNSUPPORTED_ENTITY` |
| 3D solids / meshes / Z-depth beyond point Z | Not represented | `UNSUPPORTED_ENTITY` |

To detect an incomplete import at a glance, read
`collection.metadata.has_lossy_import` (True when any entity was dropped), or the
`raw_entity_count` / `unsupported_entity_count` / `entity_count` fields for the
exact breakdown.

> ### ⚠ Known fidelity defects under remediation (CS-008)
>
> The three rows marked **silent** above are confirmed defects, reproduced
> against the golden corpus in `python/tests/fixtures/` and pinned by
> `test_geometry_characterization.py`. Until the remediation increments land:
>
> * **OCS / extrusion is a correctness defect, not a fidelity one.** A `CIRCLE`
>   drawn at OCS `(5,5)` with extrusion `(0,0,-1)` has a true WCS centre of
>   `(-5,5)`; it currently imports at `(+5,5)`. Geometry is placed **mirrored**,
>   with no diagnostic. Treat imported coordinates as untrusted for any drawing
>   whose entities carry a non-default extrusion vector.
> * **LWPOLYLINE elevation is dropped; POLYLINE elevation is kept.** Identical
>   geometry survives or is flattened depending only on which entity the
>   authoring tool emitted.
> * **A fit-point SPLINE imports as an entity with zero control points** — it
>   raises `INVALID_SPLINE`, but still enters the collection contributing no
>   geometry and no bounds.
>
> Remediation order: evidence infrastructure (done) → spline fidelity →
> coordinate correctness.

## Design guarantees

- **Neutral geometry.** ezdxf entities never leak outside the importer; only
  internal dataclasses cross the boundary.
- **Millimetres internally.** `$INSUNITS` is read and applied as a scale factor
  per the AutoCAD unit enumeration (including inch/mil/microinch/micron, which are
  easy to confuse); the *original* unit name is preserved in
  `ImportMetadata.source_units`. Absent, unitless, or unrecognized codes raise
  `UNKNOWN_UNITS` and assume a 1:1 mm scale — so an unmapped unit is flagged, not
  silently mis-scaled.
- **Immutable & read-only.** Imported geometry is frozen; future operations
  derive new geometry rather than mutating imports.
- **Advisory import.** No entity is silently discarded. Zero-length lines, zero
  radii, degenerate polylines, invalid splines, duplicate handles, and
  unsupported types all surface as `GeometryDiagnostic`s (reusing the shared
  `DiagnosticSeverity` scale).
- **Deterministic bounds.** Arc bounding boxes include cardinal bulge points, not
  just endpoints.

## Diagnostics

Stable codes in `geometry/diagnostics.py`: `UNSUPPORTED_ENTITY`, `MISSING_LAYER`,
`ZERO_LENGTH_LINE`, `ZERO_RADIUS`, `INVALID_SPLINE`, `UNKNOWN_UNITS`,
`EMPTY_FILE`, `DUPLICATE_HANDLE`, `DEGENERATE_POLYLINE`, `POLYLINE_BULGE_IGNORED`.
Degeneracy checks (zero length/radius, bulge) use a small tolerance, so float
noise from CAD exports is caught rather than slipping past an exact `== 0`.

**Reserved, not yet emitted** (CS-008 remediation): `FIT_POINT_SPLINE_UNREPRESENTED`,
`RATIONAL_SPLINE_WEIGHTS_DROPPED`, `LWPOLYLINE_ELEVATION_DROPPED`,
`EMPTY_SPLINE_GEOMETRY`, `OCS_TRANSFORM_FAILED`. The vocabulary is defined in the
registry now so it has one home; the importer begins raising these in the
increments that follow. A consumer matching on them today will simply never see
them — it will not see a differently-named finding instead.

There is deliberately **no `OCS_TRANSFORM_APPLIED` code.** A transform that
succeeds is correct importer behavior, not a defect; coding it as a diagnostic
would train readers to skim past the findings that do matter. Success is recorded
as entity/import metadata, and only *failure* earns a diagnostic.

### Loss evidence

A diagnostic says something happened; two additive fields say what it cost.

| Field | Meaning |
|-------|---------|
| `recoverable` | `True` — enough evidence survives to reconstruct the source. `False` — information is gone. `None` — the question does not apply. |
| `metadata` | Structured particulars: counts, degrees, source normals, tolerances. Never prose. |

`diagnostics.LOSS_CODES` and `is_loss(code)` name the codes that mean *source
information did not survive*, which is what separates real loss from routine
normalization. `OCS_TRANSFORM_FAILED` is excluded: it reports that a correction
could not be applied — a correctness failure, not a fidelity cost.

No separate loss-record type exists. `GeometryDiagnostic` already owns import
findings and already carries the entity context (type, handle, layer) a loss
report needs; a parallel model would split that ownership for no gain.

### Import summary

`collection.report()` returns an `ImportReport` — a flat, recomputed **view** over
entities, metadata, and diagnostics that already exist:

```python
report = import_dxf("part.dxf").report()
report.has_unrecoverable_loss   # something was lost that nothing can rebuild
report.loss_count               # vs. report.diagnostic_count
report.codes                    # sorted, de-duplicated
```

It carries **no duration or timestamp** — wall-clock would make two imports of one
file compare unequal and destabilize fixtures, for a number that says nothing
about fidelity. Because it is rebuilt on demand it cannot drift from the
collection it describes.

## Golden fixture corpus

`python/tests/fixtures/` holds an **immutable** set of ASCII DXF files, one per
fidelity question, reviewable as text. They are never regenerated by a test run —
regenerating would silently re-baseline every characterization assertion, which is
exactly the invisible change this remediation exists to prevent. Provenance and a
deliberate-regeneration path are in `fixtures/MAKE_FIXTURES.py`; to change a
fixture, add a new one and leave the old file alone.

## Serialization

Serialization **out** uses the shared reflection serializer (`to_dict`/`to_json`)
unchanged — entities carry their `kind`, so the JSON is self-describing.
Serialization **in** cannot be reflection-driven, because a heterogeneous entity
list has no single element type to reconstruct. `GeometryCollection.from_dict` /
`from_json` therefore dispatch each entity dict on its `kind` to the concrete
class, preserving global source order across a round-trip.

```python
text = collection.to_json(indent=2)
restored = GeometryCollection.from_json(text)   # order + kinds preserved
```

## Optional dependency

DXF parsing uses [`ezdxf`](https://ezdxf.mozman.at/), the project's **only**
third-party runtime dependency, kept **optional** behind the `dxf` extra so the
core still installs and tests with zero required dependencies:

```bash
pip install -e .[dxf]     # ezdxf >=1.4,<2
```

Calling `import_dxf` without `ezdxf` present raises `EzdxfNotInstalled` with an
actionable install hint. A missing, unreadable, or corrupt file raises
`DxfImportError`.

## Boundaries

This subsystem does **not** own machining operations, feeds & speeds, G-code, CAM
strategy, cut order, inside/outside determination, or execution. It is a pure,
testable, machine-independent import layer.
