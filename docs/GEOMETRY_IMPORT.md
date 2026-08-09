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
| **SPLINE** knot vectors, weights, fit points | Dropped; only control points + degree kept | (documented; hull-bounded) |
| **ELLIPSE**, **TEXT**, **MTEXT**, **HATCH**, **DIMENSION** | Not represented | `UNSUPPORTED_ENTITY` |
| **INSERT** / block references | Not expanded; block contents do not appear | `UNSUPPORTED_ENTITY` |
| 3D solids, `MESH` entities, Z-depth beyond point Z | Not represented | `UNSUPPORTED_ENTITY` |
| `POLYLINE` in a **mesh** flavour (polygon / polyface) | Vertices kept in source order as a flat chain — a mesh is not a profile, so the result is rarely meaningful as one | (none) |

To detect an incomplete import at a glance, read
`collection.metadata.has_lossy_import` (True when any entity was dropped), or the
`raw_entity_count` / `unsupported_entity_count` / `entity_count` fields for the
exact breakdown.

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
`EMPTY_FILE`, `DUPLICATE_HANDLE`, `DEGENERATE_POLYLINE`, `POLYLINE_BULGE_IGNORED`,
`OCS_TRANSFORM_FAILED`, `NON_PLANAR_GEOMETRY`.
Degeneracy checks (zero length/radius, bulge) use a small tolerance, so float
noise from CAD exports is caught rather than slipping past an exact `== 0`.

`geometry.diagnostics.CANONICAL_CODES` is the authoritative list; this paragraph
is a convenience copy, and a test asserts the two agree so it cannot drift.

### The two OCS codes are not interchangeable

DXF stores CIRCLE, ARC, LWPOLYLINE and 2D POLYLINE coordinates in the entity's
Object Coordinate System. Resolving that to world coordinates has two distinct
unhappy outcomes, and conflating them would put a false reason on the record:

| Code | What happened | Are the coordinates right? |
|---|---|---|
| `OCS_TRANSFORM_FAILED` | The transform could not be obtained or applied | **No** — left untransformed, may be misplaced |
| `NON_PLANAR_GEOMETRY` | Transform succeeded, but the result is not parallel to WCS XY | **Yes** — but a planar reading of them does not recover the authored shape |

`NON_PLANAR_GEOMETRY` is the one to watch if you need a profile: a tilted circle's
XY footprint is really an ellipse, and a tilted vertex chain's XY projection is
foreshortened. The coordinates are not wrong; the 2D reading of them is.

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
