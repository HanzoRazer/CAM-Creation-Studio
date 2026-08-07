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
| **SPLINE** fit points, weights, knots | **Preserved** — see *Splines* below | (none — nothing is lost) |
| Fit-spline **start/end tangents** | Not represented; fit points kept | `FIT_POINT_SPLINE_UNREPRESENTED` |
| **Tilted** extrusion on ARC/CIRCLE | Centre corrected; the tilted *plane* is not representable | `OCS_TRANSFORM_FAILED` |
| **ELLIPSE**, **TEXT**, **MTEXT**, **HATCH**, **DIMENSION** | Not represented | `UNSUPPORTED_ENTITY` |
| **INSERT** / block references | Not expanded; block contents do not appear | `UNSUPPORTED_ENTITY` |
| 3D solids / meshes / Z-depth beyond point Z | Not represented | `UNSUPPORTED_ENTITY` |

To detect an incomplete import at a glance, read
`collection.metadata.has_lossy_import` (True when any entity was dropped), or the
`raw_entity_count` / `unsupported_entity_count` / `entity_count` fields for the
exact breakdown.

> ### CS-008 fidelity remediation — complete for the defects verified here
>
> **Scope of this claim.** Three defects were reproduced against the golden
> corpus *in this repository* and are fixed, each guarded by a flipped
> characterization test in `test_geometry_characterization.py`. The claim covers
> exactly those three. An external CS-008 audit is referenced by the orders that
> commissioned this work but was never supplied to the implementing session, so
> nothing here establishes coverage of findings beyond the three below. See
> [SESSION_INTEGRITY_2026-08-07.md](SESSION_INTEGRITY_2026-08-07.md).
>
> * **OCS / extrusion was a correctness defect, not a fidelity one.** A `CIRCLE`
>   at OCS `(5,5)` with extrusion `(0,0,-1)` imported at `(+5,5)` instead of its
>   true WCS centre `(-5,5)` — geometry placed **mirrored**, silently. Now
>   corrected; see *Coordinate systems* below.
> * **LWPOLYLINE elevation was dropped while POLYLINE kept it.** Both now
>   preserve Z identically, so fidelity no longer depends on which entity the
>   authoring tool emitted.
> * **A fit-point SPLINE imported as an entity with zero control points.** Now
>   preserved as a fit representation; see *Splines*.
>
> Evidence infrastructure (**done**) → spline fidelity (**done**) → coordinate
> correctness (**done**).

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

Fidelity codes: `FIT_POINT_SPLINE_UNREPRESENTED`,
`RATIONAL_SPLINE_WEIGHTS_DROPPED`, `EMPTY_SPLINE_GEOMETRY`,
`OCS_TRANSFORM_FAILED`. Each fires only on genuine loss or a genuine
representational limit — never merely because a DXF feature is non-default.

`LWPOLYLINE_ELEVATION_DROPPED` stays **registered but unemitted**: elevation is
now preserved on every supported import, so nothing raises it. It is kept so the
vocabulary remains stable for consumers written against it.

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

## Coordinate systems (OCS → WCS)

DXF stores **CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE** coordinates in the
entity's own *object coordinate system*, defined by its extrusion vector. With
the default extrusion `(0,0,1)` the OCS **is** the WCS. With any other, raw
coordinates are in the wrong place.

The transform comes from **ezdxf's own `entity.ocs()`**, not a local
implementation of the arbitrary-axis algorithm — ezdxf defines DXF coordinate
semantics and is already the importer's dependency, so reimplementing it would
create a second correctness authority for the same maths. Access stays
duck-typed, so `entities.py` still imports no ezdxf symbol.

| Extrusion | Meaning | Behavior |
|-----------|---------|----------|
| `(0,0,1)` — default | OCS is WCS | **untouched**; drawings without an extrusion import exactly as before |
| `(0,0,-1)` — mirrored | still parallel to WCS XY | corrected exactly, **silently**; arc angles mirrored with the centre |
| anything else — tilted | out of the XY plane | centre corrected; `OCS_TRANSFORM_FAILED` reports that the plane itself is not representable |

`LINE` and `SPLINE` coordinates are WCS in DXF and are never transformed. A 3D
`POLYLINE` is WCS; a 2D one is OCS, decided per entity.

The source extrusion is retained on `Circle2D`, `Arc2D` and `Polyline2D` as
`extrusion` (`None` when default) — evidence only, since the coordinates are
already corrected.

> **Mirrored arcs trade endpoints.** A mirror reverses orientation, and `Arc2D`
> is defined as sweeping **counter-clockwise** from `start_angle` to `end_angle`.
> The locus and the start/end identity cannot both survive that, so the importer
> keeps the locus — the geometry — and the two endpoints swap roles. The swept
> shape and sweep magnitude match ezdxf exactly.

> **`OCS_TRANSFORM_FAILED` is not a loss code.** It reports a representational
> limit — the centre is still corrected — rather than information that failed to
> survive, so it is excluded from `LOSS_CODES` and does not raise
> `report().loss_count`.

### LWPOLYLINE elevation

An LWPOLYLINE's vertices are 2D OCS points at the entity's `elevation`; that
elevation is the Z. It is read, transformed with the vertices, scaled with the
drawing units, and coerced to plain `float` — so an LWPOLYLINE and an equivalent
POLYLINE now yield identical point Z. Bulges, widths, closure, vertex order,
handles and layers are unaffected.

Planar `Bounds` remain XY-only: Z is preserved on points, but elevation does not
redefine the bounds contract and no 3D bounds type was introduced.

## Splines

DXF defines a spline one of two ways, and they are **not** interchangeable. The
importer keeps whichever the source used rather than converting:

| `representation` | Authoritative points | Meaning |
|------------------|----------------------|---------|
| `"control"` | `control_points` | control points define the curve |
| `"fit"` | `fit_points` | the curve passes *through* these points |

`spline.defining_points` returns the authoritative list either way. Also
preserved: `knots`, `weights`, `degree`, `closed`, `periodic`, `rational`.

A fit-point spline is a **complete description, not a broken control-point one**,
so preserving it raises no diagnostic. Likewise a rational spline whose weights
survive is silent. This is the governing rule: *a loss diagnostic describes
actual information loss, never merely the presence of a non-default DXF feature.*

Deriving control points from fit points is curve fitting — real spline
mathematics — and is deliberately not done here. An importer preserves evidence;
it does not invent geometry.

**Knots and weights are never scaled** by the drawing units. Knots live in
parameter space and weights are dimensionless; multiplying either by a mm
conversion would corrupt the curve.

**Invariant:** a spline must carry the points its representation needs.
Constructing `Spline2D` with neither raises `ValueError`, and a source spline
with neither is excluded from the collection with `EMPTY_SPLINE_GEOMETRY` —
rather than admitted as an entity that counts as imported while containing
nothing.

What still costs something:

| Condition | Behavior | Signal |
|-----------|----------|--------|
| Neither control nor fit points | Entity excluded | `EMPTY_SPLINE_GEOMETRY` |
| Weight count ≠ control-point count | Weights dropped; association unrecoverable | `RATIONAL_SPLINE_WEIGHTS_DROPPED` |
| Fit spline with start/end tangents | Fit points kept; tangents not represented | `FIT_POINT_SPLINE_UNREPRESENTED` |
| Control points < degree + 1 | Kept as given | `INVALID_SPLINE` (advisory, **not** a loss) |

> **Bounds caveat.** For a control-point spline, `bounds` is the control hull — a
> superset of the curve, safe to reason about. For a **fit-point** spline it is
> not: the curve interpolates the fit points and may bulge outside their box, so
> the bounds can under-report. Tightening them requires evaluating the curve.

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
