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

A **successful import is not a guarantee of full geometric fidelity.** Most of
these are surfaced as a diagnostic or an unsupported-entity drop — but not all of
them, and the exceptions are listed as such below rather than covered by a
blanket promise. A consumer that needs faithful geometry must check them:

| Source construct | Behavior | Signal |
|------------------|----------|--------|
| Polyline **bulges** (arc segments) | Flattened to straight chords; vertices kept | `POLYLINE_BULGE_IGNORED` |
| **SPLINE** fit points, weights, knots | **Preserved** — see *Splines* below | (none — nothing is lost) |
| Fit-spline **start/end tangents** | Not represented; fit points kept | `FIT_POINT_SPLINE_UNREPRESENTED` |
| **OCS / extrusion vectors** | **Resolved to WCS** since F1. A transform that cannot be obtained or applied is reported | `OCS_TRANSFORM_FAILED` |
| **LWPOLYLINE / 2D POLYLINE** `elevation` | **Preserved.** Resolved through the OCS transform, both paths alike | (none — nothing is lost) |
| **ELLIPSE**, **TEXT**, **MTEXT**, **HATCH**, **DIMENSION** | Not represented | `UNSUPPORTED_ENTITY` |
| **INSERT** / block references | Not expanded; block contents do not appear | `UNSUPPORTED_ENTITY` |
| 3D solids, `MESH` entities, Z-depth beyond point Z | Not represented | `UNSUPPORTED_ENTITY` |
| `POLYLINE` in a **mesh** flavour (polygon / polyface) | Vertices kept in source order as a flat chain — a mesh is not a profile, so the result is rarely meaningful as one | **(none — silent)** |
| Entity **display attributes**: colour, linetype, lineweight, transparency | Not represented; the models carry `layer` and nothing else | **(none — silent)** |

To detect an incomplete import at a glance, read
`collection.metadata.has_lossy_import` (True when any entity was dropped), or the
`raw_entity_count` / `unsupported_entity_count` / `entity_count` fields for the
exact breakdown.

**Two limits are genuinely silent, and neither moves `has_lossy_import`.** They
are called out here because the rest of this page is built on the opposite habit,
and an exception that is only visible as a blank table cell is not documented:

* a **mesh-flavour `POLYLINE`** imports as an ordinary flat chain. No diagnostic
  is raised and `has_lossy_import` stays `False`, so a polyface reads as a clean
  import of a profile it never was;
* **display attributes** are dropped without a diagnostic. This one is deliberate
  and is not a defect to fix: colour and linetype are presentation, not geometry,
  and this importer's contract is geometric fidelity. It is recorded because a
  consumer looking for them will otherwise find neither the values nor a reason.

A third case is silent by construction: **unreadable elevation is read as absent
(`0.0`)**. ezdxf rejects a non-numeric elevation at assignment, so the condition
cannot be reached from a file it will open; there is no code for it because a
symbol for an undemonstrable case is how unreachable vocabulary accumulates.

## Elevation

A flat profile can sit at a height, and DXF records that height in a different
place depending on which polyline the authoring tool emitted:

| Entity | Where the height lives | Vertices |
|---|---|---|
| `LWPOLYLINE` | `dxf.elevation`, a **scalar** | at z = 0 |
| 2D `POLYLINE` | `dxf.elevation`, a **point** whose z holds the value | at z = 0 |
| 3D `POLYLINE` | nowhere — there is no elevation attribute | carry z directly |

**Elevation is the vertices' OCS z, not a value added afterwards.** It is folded
into each point *before* the OCS → WCS transform, because the transform mixes the
axes:

```text
extrusion (0,0,-1),  elevation 25   ->  z = -25          (sign flips)
extrusion (0.3,0.4,0.866), elev 25  ->  z ≈ 21.65, and x and y move too
```

Resolving XY first and adding elevation afterwards would land at `+25` in both
cases — wrong on every non-default extrusion, while still passing any test that
merely asked whether z survived.

**Equivalent authored geometry normalizes equivalently.** The same square at the
same height resolves to the same WCS coordinates whether the exporter wrote an
`LWPOLYLINE` or a 2D `POLYLINE`. This is verified across units × extrusion ×
elevation sign, each case checked both against the other representation and
against ezdxf's own transform as an independent oracle.

A 3D `POLYLINE` is **not** given an elevation — it has none, and reading one
would double-count the z its vertices already carry. Mesh flavours are likewise
untouched.

> **Historical note.** An earlier revision claimed `LWPOLYLINE` dropped elevation
> while `POLYLINE` kept it. **That asymmetry was never real.** It came from
> comparing a 2D representation against a *3D* polyline — two different things —
> and the audit's probe P8c disproved it. The fixtures
> `lwpolyline_elevation.dxf` and `polyline2d_elevation.dxf` are the correct
> paired control that replaces it.

## Source provenance

Every imported entity records where it came from:

```python
entity.source        # SourceReference | None
entity.source.entity_type   # "LWPOLYLINE" — the DXF type, not the model kind
entity.source.handle        # source handle, or None if the file has none
entity.source.layer         # source layer name
entity.source.ordinal       # position in the modelspace
```

Two properties are worth knowing before relying on it:

- **`ordinal` is the modelspace position, not the collection index.** They differ
  whenever an entity was dropped, and the gap is the evidence: ordinals `0, 2`
  record that modelspace entity 1 did not survive. Collection position is already
  available from list order.
- **`source` does not affect geometry equality.** Two identical shapes compare
  equal whether or not they share a handle. Provenance is serialized and
  inspectable, but it does not redefine what it means for two pieces of geometry
  to be the same. Compare `.source` directly when identity is the question.

`entity_type` also distinguishes what `kind` cannot: an `LWPOLYLINE` and a 2D
`POLYLINE` both become `Polyline2D`, and only provenance says which was written.

## Layer evidence

| Source condition | Meaning | Finding |
|---|---|---|
| layer attribute absent | the entity is on layer `"0"` | none |
| `layer = "0"` | a real, ordinary layer | none |
| `layer = ""` | names nothing | `MISSING_LAYER` |
| name absent from the layer table | resolves to nothing | `MISSING_LAYER` |

The first row is the one that keeps this honest: in DXF an omitted layer group
code **means** layer `"0"`. Treating omission as a defect would fire on ordinary
valid files.

A layer finding never withholds geometry — the entity is imported and the finding
rides alongside it. It is raised for unsupported entity types too, since the layer
of a dropped entity is still a fact about the source. When the document's layer
table cannot be read, the unknown-reference check is skipped rather than guessed,
because assuming an empty table would make every entity look like a bad reference.

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
- **Advisory import.** No *entity* is silently discarded. Zero-length lines, zero
  radii, degenerate polylines, invalid splines, duplicate handles, and
  unsupported types all surface as `GeometryDiagnostic`s (reusing the shared
  `DiagnosticSeverity` scale). The guarantee is entity-level and does not extend
  to every property of an entity that survives — see the two silent limits under
  *fidelity limits* above.
- **Deterministic bounds.** Arc bounding boxes include cardinal bulge points, not
  just endpoints.

## Diagnostics

Stable codes in `geometry/diagnostics.py`: `UNSUPPORTED_ENTITY`, `MISSING_LAYER`,
`ZERO_LENGTH_LINE`, `ZERO_RADIUS`, `INVALID_SPLINE`, `UNKNOWN_UNITS`,
`EMPTY_FILE`, `DUPLICATE_HANDLE`, `DEGENERATE_POLYLINE`, `POLYLINE_BULGE_IGNORED`,
`OCS_TRANSFORM_FAILED`, `NON_PLANAR_GEOMETRY`,
`FIT_POINT_SPLINE_UNREPRESENTED`, `RATIONAL_SPLINE_WEIGHTS_DROPPED`,
`LWPOLYLINE_ELEVATION_DROPPED`, `EMPTY_SPLINE_GEOMETRY`.
Degeneracy checks (zero length/radius, bulge) use a small tolerance, so float
noise from CAD exports is caught rather than slipping past an exact `== 0`.

`geometry.diagnostics.CANONICAL_CODES` is the authoritative list; this paragraph
is a convenience copy, and a test asserts the two agree so it cannot drift.

### Vocabulary status (classified at CS-008R closure)

Every registered code is **live** or **reserved**. Nothing is retired: no code has
ever been removed, and none is being removed now. "Live" is evidenced by an
emission site in this repository, not by intent.

| Code | Status | Emitted at |
|---|---|---|
| `UNSUPPORTED_ENTITY` | live | `entities.py:539` |
| `MISSING_LAYER` | live | `entities.py:379` |
| `ZERO_LENGTH_LINE` | live | `entities.py:401` |
| `ZERO_RADIUS` | live | `entities.py:432`, `:460` |
| `INVALID_SPLINE` | live | `entities.py:600`, `:611`, `:674` |
| `UNKNOWN_UNITS` | live | `importer.py:84` |
| `EMPTY_FILE` | live | `importer.py:125` |
| `DUPLICATE_HANDLE` | live | `importer.py:107` |
| `DEGENERATE_POLYLINE` | live | `entities.py:486`, `:522` |
| `POLYLINE_BULGE_IGNORED` | live | `entities.py:490`, `:526` |
| `FIT_POINT_SPLINE_UNREPRESENTED` | live | `entities.py:661` |
| `RATIONAL_SPLINE_WEIGHTS_DROPPED` | live | `entities.py:644` |
| `OCS_TRANSFORM_FAILED` | live | `entities.py:316`, `:332` |
| `NON_PLANAR_GEOMETRY` | live | `entities.py:287`, `:426`, `:455` |
| `EMPTY_SPLINE_GEOMETRY` | live | `entities.py:617` |
| `LWPOLYLINE_ELEVATION_DROPPED` | **reserved** | *(nothing emits it)* |

**Reserved: `LWPOLYLINE_ELEVATION_DROPPED`.** It was registered for the defect F5
fixed — elevation is preserved, so nothing emits it, and a closure probe confirms
no fixture in the corpus produces it.

Retiring it was considered at closure and **refused**. It is public vocabulary
with unknown external consumers; a consumer matching on the exact code name would
break for no gain beyond tidiness, and the cost of keeping an unreachable constant
is a documentation line. Compatibility outranks vocabulary hygiene here. The
classification is enforced by a test, so if anything ever emits it the claim fails
loudly instead of going quietly false.

It is equally deliberately **not** repurposed: giving an existing code a new
meaning would make historical findings ambiguous, and a "dropped elevation" symbol
should not quietly come to mean something else.

There is no malformed-elevation code. ezdxf rejects non-numeric elevation at
assignment, so the condition cannot be demonstrated, and naming a symbol for an
undemonstrable case is how unreachable vocabulary accumulates. Unreadable
elevation is read as absent (0.0) and stays silent.

There is deliberately **no `OCS_TRANSFORM_APPLIED` code.** A transform that
succeeds is correct importer behavior, not a defect; coding it as a diagnostic
would train readers to skim past the findings that do matter. Success is recorded
as entity/import metadata, and only *failure* earns a diagnostic.

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

### Loss evidence

A diagnostic says *something happened here*. Two additive fields say *what it
cost*:

| Field | Meaning |
|---|---|
| `recoverable` | Whether enough evidence survives to reconstruct the source. `None` means the question does not apply — an advisory that costs nothing. |
| `metadata` | The structured particulars: counts, degrees, source normals, tolerances. Never prose; prose belongs in `message`. |

#### `metadata` is a JSON contract, enforced at construction

The schema is deliberately open — the particulars worth recording differ per
finding — so the constraint is on **values**, not on a fixed set of keys.

**Permitted:** `str`, `int`, `float` (finite), `bool`, `None`, `list`, and `dict`
with string keys, nested to any depth. Anything else raises immediately from
`GeometryDiagnostic.__post_init__`, so no construction path can bypass it.

**Rejected, and why it matters more than it looks:**

| Value | Without the check |
|---|---|
| `tuple` | Serializes fine, returns a `list`, **compares unequal** |
| non-string key | Serializes fine, returns stringified, **compares unequal** |
| `nan` / `inf` | Emits bare `nan`, which is **not valid JSON** |
| `Point`, `set`, other objects | `TypeError` at export, naming the serializer rather than the culprit |

The first three are the reason this is enforced rather than documented. A
diagnostic is an export artifact; a value that survives in memory but changes
shape crossing JSON surfaces later as a mystifying fixture or snapshot mismatch,
far from the code that inserted it. Record a `Point` as `[x, y, z]` or as separate
keys.

`LOSS_CODES` names the codes meaning *source information did not survive*, and
`is_loss(code)` tests membership. That is what separates real loss from routine
normalization.

The two OCS codes land on opposite sides of that line, which is the sharpest
illustration of where the line is:

- `OCS_TRANSFORM_FAILED` is **not** a loss code. It reports that a correction
  could not be applied — a correctness failure, not a fidelity cost.
- `NON_PLANAR_GEOMETRY` **is** a loss code. The transform succeeded and no
  coordinate is misplaced, but the entity's *plane* is not representable here and
  the models store no extrusion, so the authored orientation is genuinely gone. A
  tilted circle read back as a `Circle2D` is not the circle that was drawn.

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

That rule has already been exercised. `polyline_elevated.dxf` was built with
`add_polyline3d` while documenting itself as an elevation control, and it is the
origin of the withdrawn LWPOLYLINE/POLYLINE asymmetry. It keeps its name and is
never reused; the correct paired control was added alongside it as
`lwpolyline_elevation.dxf` and `polyline2d_elevation.dxf`. `MAKE_FIXTURES.py`
records why, in place, so the mistake cannot be repeated by someone reading only
the generator.

### Implementation map — CS-008R F5/F6/F7

| Finding | Implementation | Tests |
|---|---|---|
| **F5** elevation | `entities.py::_source_elevation` + both polyline branches | `test_geometry_elevation.py`, fixtures `lwpolyline_elevation.dxf` / `polyline2d_elevation.dxf` |
| **F6** provenance | `models.py::SourceReference`, `entities.py::source_reference`, ordinal from `importer.py` | `test_geometry_provenance.py` |
| **F7** layer evidence | `entities.py::layer_condition`, `importer.py::_layer_table_names` | `test_geometry_layers.py` |

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

### Numeric types on the LWPOLYLINE path (accepted limitation, CS-008R F9)

ezdxf returns LWPOLYLINE vertex coordinates as `numpy.float64`, and that path is
the one place the importer does not coerce them back to a plain `float`. Every
other entity path does. `numpy` is not a declared dependency; it arrives
transitively through ezdxf.

This is **accepted, not overlooked** — ruled at CS-008R closure after probing the
whole contract surface. `numpy.float64` subclasses `float`, so value equality,
arithmetic, `math.isfinite`, the JSON metadata contract, `json.dumps`, the
`to_dict` / `from_dict` round-trip, and entity equality all behave correctly, and
a serialized document contains ordinary JSON numbers that reparse as plain
`float`. Nothing downstream can observe a difference in *behaviour*.

One artefact is observable and is recorded rather than hidden: the dataclass
`repr` renders `Point(x=np.float64(10.0), ...)` in debug output and logs. It does
not reach the CLI or any serialized artefact.

What would reopen this: a consumer that requires an exact `type(x) is float`, or
the repr surfacing in a user-facing artefact. Absent either, a coercion here
would be cleanup without evidence of impact, which closure is not the place for.

## Boundaries

This subsystem does **not** own machining operations, feeds & speeds, G-code, CAM
strategy, cut order, inside/outside determination, or execution. It is a pure,
testable, machine-independent import layer.
