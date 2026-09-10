# Toolpath Contract

**Order:** CS-015 (Commit 5)
**Status:** Architecture **selected**. Owner ratification is merge of the CS-015
PR. After merge this document is the governing planned-motion contract.
**Implements in:** CS-016 (dataclasses, IDs, serialization, preview projection).
**Does not implement:** contour/pocket/drill algorithms, compensation math,
G-code emission.

```text
Candidate A — existing preview model
Disposition: REJECT AS CANONICAL
Role: projection / view representation

Candidate B — new controller-neutral motion model
Disposition: SELECTED AS CANONICAL

Candidate C — G-code Move / ArcMove
Disposition: REJECT AS CANONICAL
Role: downstream translation representation
```

Evidence: [`TOOLPATH_CURRENT_STATE.md`](TOOLPATH_CURRENT_STATE.md),
[`TOOLPATH_CONTRACT_CANDIDATES.md`](TOOLPATH_CONTRACT_CANDIDATES.md),
[`TOOLPATH_OWNERSHIP_MATRIX.md`](TOOLPATH_OWNERSHIP_MATRIX.md),
`tools/studies/toolpath_contract_probe.py`.

This file contains **no open design notes**. CS-016 implements this shape; it
does not re-open A vs B vs C.

---

## What a toolpath is

A CAM-Creation-Studio toolpath is **ordered, controller-neutral cutter-center
motion** derived from an `OperationPlan` plus a `ToolpathStrategy`.

It is not imported geometry, not an operation definition, not a feed
recommendation, not a preview segment list, and not G-code.

```text
GeometryCollection
    ↓
GeometryWorkspace
    ↓
OperationDefinition + OperationBinding + OperationFeedRecommendation
    ↓
ToolpathStrategy
    ↓
ToolpathPlan          ← canonical motion (this document)
    ↓
preview projection    → existing ToolpathSegment (lossy view)
    ↓
semantic G-code adapter (future) → Move / ArcMove → dialect formatter
```

---

## Why preview is not canonical

`preview.ToolpathSegment` is a **view of motion that already exists**. Today
that input is G-code (`build_toolpath_model`). After CS-016 the input is
`ToolpathPlan` via a projection adapter.

It cannot be canonical because:

* `source_command` is a G-word (`G0`–`G3`);
* analytic arcs are incomplete (no center/radius/sweep) or tessellated
  (`model_from_moves`);
* lineage is a G-code line index, not `OperationDefinition` / `GeometryRef`;
* `burn` / `extrude` are G-code-family classifications, not CNC planning kinds;
* it has no strategy fingerprint or staleness.

**Disposition:** **projected into**. Not wrapped. Not stored on `ToolpathPlan`.

---

## Why G-code `Move` / `ArcMove` are not canonical

They are the body of `GCodeProgram`. `MoveType` wire values are `"G0"`…`"G3"`.
Axes may be `None` (modal omit). `feed` is the F-word. `e` is Marlin
extrusion. The program envelope carries dialect identity.

**Disposition:** **translation target** of a future `toolpath_to_gcode_program`.
Not wrapped. Not stored on `ToolpathPlan`. Planners must not emit G-code text.

---

## Why browser/JS motion is not canonical

`app/main.js` move dicts and canvas `{kind, poly, z}` segments, and
`src/gcode/generator.js`, are **legacy prototypes / UI views**. They do not
define the Python core contract. See
[`TOOLPATH_CURRENT_STATE.md`](TOOLPATH_CURRENT_STATE.md)
§ Browser / Legacy Prototype Motion Surfaces.

```text
The Python controller-neutral toolpath contract established by
CS-015/CS-016 is authoritative for the product core.

Existing browser-side motion/path objects are consumers, adapters,
legacy prototypes, or candidates for later migration; they do not
define the core motion contract.
```

---

## Canonical types (CS-016)

Names below are **mandatory** for CS-016 unless a mechanical rename is
approved. The study probe used a `Study*` prefix; production drops that prefix.

```python
@dataclass(frozen=True, slots=True)
class ToolpathStrategy:
    travel_height_mm: float
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    peck_depth_mm: float | None = None
    retract_height_mm: float | None = None
    # plus entry/lead/tab parameters as later orders add them — never G-words
    label: str = ""   # presentation; excluded from fingerprints

@dataclass(frozen=True, slots=True)
class ToolpathPlan:
    id: str
    version: str                      # document version, e.g. camstudio_toolpath_v1
    operation_definition_id: str      # exactly one generating definition
    geometry_ids: tuple[str, ...]     # selection members; no geometry copies
    binding_id: str                   # explicit; not only recoverable via the plan
    recommendation_id: str | None
    planned_feed_mm_min: float | None
    strategy_fingerprint: str
    upstream_fingerprint: str         # staleness vs geometry/definition/binding/…
    paths: tuple[OperationPath, ...]

@dataclass(frozen=True, slots=True)
class OperationPath:
    id: str
    motions: tuple[LinearMotion | ArcMotion, ...]
    depth_mm: float | None = None     # pass magnitude; not target_depth_mm

class MotionKind(str, Enum):
    TRAVEL = "travel"
    CUT = "cut"
    PLUNGE = "plunge"
    RETRACT = "retract"

@dataclass(frozen=True, slots=True)
class LinearMotion:
    id: str
    kind: MotionKind
    start: Point                      # shared.geometry.Point, millimetres
    end: Point
    planned_feed_mm_min: float | None = None
    geometry_ids: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ArcMotion:
    id: str
    kind: MotionKind                  # normally CUT
    start: Point
    end: Point
    center: Point                     # absolute mm; not G-code I/J
    radius: float
    clockwise: bool
    sweep_rad: float                  # signed; full circle allowed (start == end)
    planned_feed_mm_min: float | None = None
    geometry_ids: tuple[str, ...] = ()
```

Use `cam_creation_studio.shared.geometry.Point`. Do not introduce a
preview-local `Point` on the canonical model.

### Forbidden on these types

No fields or values equivalent to:

```text
G0 G1 G2 G3 M3 M5 F-word S-word N-word
source_command  MoveType  dialect  controller  postprocessor
grbl marlin linuxcnc fanuc mach masso
machine_ready  safe  approved  production_ready
```

Travel height is `travel_height_mm`, not `safe_height`. It is a planned Z,
not a safety certificate.

Canonical serialization must not contain preview type names (`ToolpathSegment`)
or G-code type names (`Move`, `ArcMove`).

`MotionKind` has no `burn` or `extrude` members. Those remain preview/G-code
classifications of other machine families.

---

## Linear motion

A `LinearMotion` is an explicit pose-to-pose segment. Unset axes are **not**
allowed: both `start` and `end` are complete millimetre points (D7, contrast
G-code modality).

Kinds:

| Kind | Meaning |
|---|---|
| `travel` | Non-cutting relocation, including XY at travel height |
| `plunge` | Feed into the work along Z (or a steep approach) |
| `cut` | Material-engaging feed (typically XY at pass depth) |
| `retract` | Leave the work, typically to travel/retract height |

Kind is stored. Z sign is not a substitute for kind (a plunge and a retract
can share a Z coordinate at the handoff).

---

## Analytic arcs

`ArcMotion` is canonical when the motion is circular in XY (helical Z may
interpolate `start.z` → `end.z` along the sweep).

Required: start, end, center, radius, clockwise, sweep.

* Clockwise true ⇒ `sweep_rad` ≤ 0; false ⇒ `sweep_rad` ≥ 0.
* Coincident start/end is a full turn (|sweep| = 2π), not an empty move.
* Reflex arcs (|sweep| > π) are stored, not split into tessellation.
* Plane: XY for CS-016. Other planes are out of scope until a later order.

Tessellation (`shared.geometry.interpolate_arc`) is a **renderer** helper.
It is not storage.

Do not store I, J, or R. Those are G-code words produced later from center
and start.

---

## Z / depth

```text
target_depth_mm     OperationDefinition — final intended depth (unchanged)
stepdown / DOC      ToolpathStrategy
depth_mm            OperationPath — generated pass magnitude
start.z / end.z     actual machine-space Z on each motion
travel_height_mm    strategy — planned travel Z, not “safe”
```

Example: target 12 mm, stepdown 3 mm → paths at 3, 6, 9, 12. Cutting Z is
typically negative of the magnitude when Z=0 is stock top. That convention is
a generator concern; the definition field is never rewritten to a pass Z.

---

## Feeds

```text
recommendation_id      provenance to CS-014 (optional if none exists)
planned_feed_mm_min    planned path feed on the plan (optional per-motion)
execution feed         not represented
```

Selected provenance model: **recommendation ID plus planned path feed**.
ID-only cannot round-trip a planner override. Feed-only loses why the number
was chosen. Neither number is an F-word.

`recommended feed ≠ planned path feed ≠ validated execution feed`.

---

## Binding

`ToolpathPlan.binding_id` is **required** for machining paths. Recoverability
through `OperationPlan` is not enough: a persisted path must still name the
binding after the plan document is not in hand.

Tool diameter used for compensation is resolved from that binding’s catalog
`Tool` at generation time and captured in `upstream_fingerprint`, not by
copying diameter onto every motion.

---

## Drilling

No canned-cycle object. `DrillDefinition.peck_depth_mm` /
`retract_height_mm` remain **intent**. Strategy expands:

```text
travel to hole XY at travel height
plunge to successive depth magnitudes (peck or single)
retract to retract height between pecks
retract to travel height when done
```

Those motions are ordinary `LinearMotion` values.

---

## Compensation and direction

Planner owns **explicit cutter-center geometry**.

| `ContourRelation` | Cutter-center vs source |
|---|---|
| ON | offset 0 |
| INSIDE | offset toward interior by tool radius |
| OUTSIDE | offset toward exterior by tool radius |

Offset happens in strategy/generation, not in CS-012, not in G-code (no G41).

`CutDirection` (climb / conventional / unspecified) orients or reverses the
**generated** path. Source winding is not mutated.

CS-016 does not implement offset algorithms. CS-017 contour planner does,
against this contract.

---

## Engagement

DOC, WOC, stepdown, and stepover are **ToolpathStrategy** parameters. They
are not added to CS-012 or CS-014.

---

## Identifiers

Deterministic: `cam_creation_studio.shared.ids.stable_id` from creation
context (kind, poses, indices, parent ids) — same doctrine as CS-011–CS-014.
Same planning inputs and strategy ⇒ same plan id, path ids, motion ids,
order, and serialized bytes (D11).

No `uuid4` for canonical path identity.

---

## Preview seam

```text
ToolpathPlan  →  toolpath_to_preview  →  list[ToolpathSegment]
```

Adapter rules (proven by the study probe):

* `travel` / `retract` → preview `travel` (feed `None`)
* `cut` / `plunge` → preview `cut`
* `ArcMotion` → preview `arc`
* `source_command` left empty — the adapter must not invent G-words
* distance from shared geometry (`distance` / `arc_length`)

**Projection loss (accepted):** planning IDs, fingerprints, plunge vs retract
kind, arc center/radius/sweep/clockwise, planned vs recommended feed,
`OperationPath.depth_mm`. Loss is **not** justification to put those fields
onto `ToolpathSegment` in CS-015 (D16) or to weaken `ArcMotion`.

Until CS-016 lands, `build_toolpath_model` remains the G-code→preview bridge.
That is the **prior/current** preview pipeline, not the planned-motion
authority.

---

## G-code seam

```text
ToolpathPlan
    ↓  semantic adapter (future)
Move / ArcMove inside GCodeProgram
    ↓  dialect formatter
text
```

| Toolpath semantic | G-code-domain semantic |
|---|---|
| travel linear | rapid move |
| feed linear (`cut`) | feed move |
| plunge | feed move (Z) |
| retract | rapid move (Z) |
| clockwise arc | CW arc |
| counter-clockwise arc | CCW arc |

No formatted G-code text in the toolpath package. Dialect begins at
`gcode.dialects`.

---

## Persistence

Plans **may be persisted** as a versioned document with
`strategy_fingerprint` and `upstream_fingerprint`. See
[`TOOLPATH_LINEAGE_AND_STALENESS.md`](TOOLPATH_LINEAGE_AND_STALENESS.md).

Always-derived-only was rejected: path generation will be expensive enough
that stored plans need an explicit stale bit, matching CS-014 recommendations.

---

## Package placement (CS-016)

New production package `cam_creation_studio.toolpath`.

* Must not import `gcode` except a future dedicated adapter module.
* Must not store preview types.
* Preview may import toolpath to project (preferred) **or** toolpath may
  depend on preview **only** in an adapter module that constructs
  `ToolpathSegment` at the boundary — never as canonical storage.
* `operations` must not import toolpath in CS-016 if that would invert
  `toolpath → operations` (toolpath reads an `OperationPlan`; it does not
  write into it). D1.

The study file `tools/studies/toolpath_contract_probe.py` is **not** that
package. Production must not import it.

---

## Conceptual API (CS-016)

```python
build_toolpath_plan(operation_plan, definition_id, strategy) -> ToolpathPlan
toolpath_to_preview(toolpath_plan) -> list[ToolpathSegment]
```

`build_toolpath_plan` in CS-016 may accept **already-constructed** paths for
contract tests, or a trivial placeholder path. It must not ship contour
offset or pocketing. Machining algorithms start at CS-017.

Downstream only:

```python
toolpath_to_gcode_program(toolpath_plan, dialect_context) -> GCodeProgram
```
