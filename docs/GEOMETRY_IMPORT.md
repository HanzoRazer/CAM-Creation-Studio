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

## Design guarantees

- **Neutral geometry.** ezdxf entities never leak outside the importer; only
  internal dataclasses cross the boundary.
- **Millimetres internally.** `$INSUNITS` is read and applied as a scale factor;
  the *original* unit name is preserved in `ImportMetadata.source_units`. Absent
  or unitless drawings raise `UNKNOWN_UNITS` and assume a 1:1 mm scale.
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
`EMPTY_FILE`, `DUPLICATE_HANDLE`, `DEGENERATE_POLYLINE`.

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
