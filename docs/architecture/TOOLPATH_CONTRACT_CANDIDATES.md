# Toolpath Contract Candidates

**Order:** CS-015 (Commit 2)
**Status:** Comparison complete. This document selects a candidate **as the
study’s architectural conclusion**. The governing field-level contract is
[`TOOLPATH_CONTRACT.md`](TOOLPATH_CONTRACT.md) (Commit 5). Until that file
exists, treat the selection here as the comparison result, not yet the
ratified product contract.
**Evidence base:** [`TOOLPATH_CURRENT_STATE.md`](TOOLPATH_CURRENT_STATE.md)
surveyed at `ceeefba`.

CS-015 must choose **one** canonical planned-motion authority. The three
candidates required by the order:

| ID | Candidate | Exists in repo today? |
|---|---|---|
| **A** | Existing preview model (`ToolpathSegment` / `Segment`) | Yes |
| **B** | New controller-neutral motion model | **No** (defined here; proven in the study prototype) |
| **C** | Existing G-code motion domain (`Move` / `ArcMove`) | Yes |

A fourth informal candidate — browser `state.moves` / canvas `manualSegs` —
was inventoried and excluded from this matrix. It is a legacy prototype, not
a Python-core contract ([`TOOLPATH_CURRENT_STATE.md`](TOOLPATH_CURRENT_STATE.md)
§ Browser / Legacy Prototype Motion Surfaces).

---

## What “canonical” must mean

A CAM-Creation-Studio toolpath is **planned cutter motion** derived from
manufacturing-planning artifacts. It must answer “why does this motion exist?”
and it must sit **between** `OperationFeedRecommendation` and G-code:

```text
Geometry → Workspace → Definition → Binding → Advisory feeds
        → [canonical toolpath]
        → preview projection
        → semantic G-code translation
        → dialect formatting
```

Constitutional constraints that immediately disqualify a candidate if it
cannot be met without rewriting its identity:

| Constraint | Source |
|---|---|
| No G0/G1/G2/G3, M-codes, F/S/N words on the contract | CS-015 D5 |
| No dialect identity | D6 |
| Analytic arcs where an arc exists; tessellation is a view | D8 |
| Millimetres only | D7 |
| Lineage to the generating operation (and geometry) | D12 |
| Deterministic IDs, order, serialization | D11 |
| Not stored inside geometry / workspace / definition / binding / recommendation | D1 |
| Planner does not self-certify (`safe`, `approved`, …) | D14 |
| Preview and G-code behavior remain unchanged this order | D15, D16 |

---

## Candidate sketches

### A — Existing preview model

```text
List[ToolpathSegment]
  type: travel | cut | extrude | arc | burn
  start, end: preview Point
  feed, z, line
  source_command: 'G0'..'G3'
  distance
```

Built **from G-code** (`build_toolpath_model`). Older entry point
`model_from_moves` tessellates G2/G3 into linear `Segment`s.

### B — New controller-neutral motion model

Conceptual shape (names may be finalized in Commit 5):

```text
ToolpathPlan
  id
  operation_definition_id
  geometry_ids
  binding_id
  recommendation_id?          # provenance, not execution authority
  planned_feed_mm_min?        # planned path feed ≠ recommended feed
  strategy_fingerprint
  paths: tuple[OperationPath, ...]

OperationPath
  id
  motions: tuple[LinearMotion | ArcMotion, ...]

LinearMotion / ArcMotion
  explicit start/end (mm)
  motion kind (travel | cut | plunge | retract) — not a G-word
  ArcMotion: center, radius, clockwise, sweep — not I/J, not G2/G3
```

Does not exist in production. The study prototype must prove it can represent
linear motion, analytic arcs (including reflex and full-circle), Z, lineage,
deterministic serialization, and projection into **existing**
`ToolpathSegment` without storing `ToolpathSegment` / `Move` / `ArcMove`.

### C — Existing G-code motion domain

```text
GCodeProgram
  header.machine, safe_z, spindle_…
  moves: [Move | ArcMove]
  footer.end_code  # M30 etc.

Move.type    = MoveType.RAPID | LINEAR     # "G0" | "G1"
ArcMove.type = MoveType.ARC_CW | ARC_CCW   # "G2" | "G3"
optional x/y/z/feed/e/i/j/r  (None = G-code modal omit)
```

Built for generation, parse round-trip, and dialect formatting.

---

## Comparison matrix

Ratings: **meets** / **partial** / **fails**. “Partial” means the concern is
representable only by overloading a field or by a later rewrite that would
change the type’s identity.

| Concern | A Preview model | B New neutral model | C G-code model |
|---|---|---|---|
| **controller-neutral** | **fails** — `source_command` is a G-word; laser/Marlin kinds (`burn`, `extrude`) are dialect-family classifications | **meets** — kinds are planning vocabulary (`travel`, `cut`, `plunge`, `retract`); no G/M/F/S words, no dialect field | **fails** — `MoveType` values **are** `"G0"`…`"G3"`; `feed` is the F-word; `e` is Marlin; header `machine` is a dialect id |
| **analytic arcs** | **partial** — `build_toolpath_model` keeps one `arc` segment but stores only endpoints + length + G2/G3; no center/radius/sweep; `model_from_moves` tessellates | **meets** — first-class center, radius, direction, sweep; tessellation is projection-only | **partial** — I/J or R is analytic **in G-code form**; no explicit center, no stored sweep; negative R is a G-code major-arc convention |
| **3D/Z motion** | **partial** — endpoint Z exists; plunge vs retract vs travel height is not a kind | **meets** — explicit XYZ poses plus motion kind; pass Z is a path property, not a redefinition of `target_depth_mm` | **partial** — optional Z word with **modal omit**; “keep previous Z” is a controller rule, not an explicit pose |
| **geometry lineage** | **fails** — `line` indexes G-code, not `GeometryRef` | **meets** — plan-level `geometry_ids`; per-motion refs as needed without copying geometry | **fails** — no geometry IDs |
| **operation lineage** | **fails** — no `OperationDefinition` id | **meets** — exactly one `operation_definition_id` per plan | **fails** — no operation IDs |
| **feed semantics** | **fails** — copies the F-word; cannot distinguish recommended vs planned vs execution; travel feed is `None` only by G0 heuristic | **meets** — recommendation id as provenance **and** a separate planned path feed; travel/plunge kinds do not require a G0 rule | **fails** — `feed` **is** the F-word; modal and dialect-shaped |
| **deterministic serialization** | **partial** — frozen dataclasses, but no document version, fingerprint, or stable IDs; list order follows G-code | **meets** — content-addressed IDs (`stable_id`), ordered tuples, versioned dict/JSON, strategy fingerprint | **partial** — `GCodeProgram.to_json` is deterministic for a given program, but IDs/lineage/fingerprint vs planning inputs do not exist |
| **preview compatibility** | **meets** — it **is** the preview model | **meets** — one-way adapter onto existing `ToolpathSegment` (lossy by policy, not by weakening B) | **partial** — `build_toolpath_model` already consumes `Move`/`ArcMove`; using C as canonical would make preview a second copy of G-code |
| **G-code translation** | **fails** as a *source* — A is already a projection **from** G-code; mapping A back to G-code would invert a lossy view (tessellation, missing center) | **meets** — semantic map: travel linear → rapid move, feed linear → feed move, CW/CCW arc → CW/CCW arc; then `Move`/`ArcMove` then formatter | **meets** — C **is** the G-code-domain object; but that collapses “planning” into “already posted” |
| **legacy coupling** | **fails** — CS-003 named it canonical for *preview of G-code*; `source_command`; duplicate preview `Point`; burn/extrude kinds | **meets** — new type; production modules do not import the study probe; D15/D16: existing preview/G-code unchanged | **fails** — generator, parser, validator, preflight, golden fixtures, dialects, Marlin E-word |

---

## Concern-by-concern narrative

### Controller neutrality

A and C fail D5/D6 on identity, not on a missing helper. Promoting either to
“planned toolpath” would smuggle G-code into CS-016 dataclasses. B is the only
candidate whose vocabulary can be `travel`/`cut`/`plunge`/`retract` without
lying about what the fields mean.

Laser `burn` and Marlin `extrude` stay on A (and on C’s `e` / laser dialects).
They are **not** CNC manufacturing motion kinds for the planned-path contract.

### Analytic arcs

D8: tessellation may occur for rendering; it must not be canonical storage.

* A’s older builder tessellates; the newer `ToolpathSegment` of type `arc`
  still cannot round-trip a center or a reflex sweep without `source_command`.
* C stores G-code arc words, including signed R.
* B stores geometric arcs (start, end, center, radius, clockwise, sweep).
  Full-circle (`start == end`, sweep = ±2π) is representable without a G-code
  “omitted XY” trick.

Imported `Arc2D` (DXF CCW degrees) is **source geometry**, not a candidate.
B may be *derived from* `Arc2D` later; it does not store `Arc2D`.

### Z / depth

CS-012 `target_depth_mm` is final intended depth. Pass decomposition must not
live on that field.

A and C can *emit* Z coordinates but cannot name a pass (`z=3` vs `z=6`) as
strategy-owned levels. B can: one `OperationPath` per depth level, each with
explicit motion Z, while the definition’s `target_depth_mm` stays 12.

Plunge and retract are motion kinds on B, not G0/G1 guesses from Z sign.

### Lineage

Neither A nor C traces to `OperationDefinition` or `GeometryRef`. That is a
hard fail of D12, not a documentation gap.

B carries:

* exactly one `operation_definition_id`;
* `geometry_ids` from the selection (no geometry copies for lineage);
* `binding_id` on the plan (explicit, not only recoverable by walking the
  operation plan);
* `recommendation_id` as provenance, plus `planned_feed_mm_min` as a
  **separate** planned value.

### Feeds

CS-014 output is advisory. Copying `FeedRecommendation.feed_rate` into a
G-word (A/C) collapses recommended / planned / execution into one number.

B keeps three distinct facts:

```text
recommended feed     → recommendation_id (+ wrapped FeedRecommendation on the plan)
planned path feed    → planned_feed_mm_min on the toolpath
execution feed       → not represented (operator / later G-code translation)
```

### Preview and G-code seams

Required direction:

```text
Canonical toolpath → preview projection
Canonical toolpath → semantic G-code adapter → GCodeProgram → dialect formatter
```

A inverts the first arrow (preview is built from G-code). C inverts the
second (the “toolpath” already *is* `GCodeProgram` moves). B preserves both
arrows. Projection into today’s `ToolpathSegment` **will lose** center,
sweep, kinds finer than travel/cut, and planning IDs. That loss is
documented as projection loss, not a reason to weaken B.

Planners must not emit G-code text. A and C make that prohibition awkward
because they already *are* G-code-adjacent. B makes it structural.

### Legacy coupling

Choosing A or C as canonical would force CS-016 to either (a) reuse types
that violate D5, or (b) silently redefine `ToolpathSegment` / `Move` until
preview and G-code break (forbidden by D15/D16). B adds a new authority and
leaves existing types in their current roles.

---

## Explicit selection (comparison conclusion)

```text
Candidate A — existing preview model
Disposition: REJECT AS CANONICAL
Role: projection / view representation of motion that already exists
      (today: of G-code; after CS-016: of canonical toolpaths)

Candidate B — new controller-neutral motion model
Disposition: SELECTED AS CANONICAL
Role: planned cutter-center motion derived from OperationPlan + strategy

Candidate C — G-code Move / ArcMove
Disposition: REJECT AS CANONICAL
Role: downstream translation representation inside GCodeProgram
```

**Why B wins:** it is the only candidate that can satisfy controller
neutrality, analytic-arc storage, operation/geometry lineage, and the
recommended-vs-planned feed split **without** changing the identity of
preview or G-code types.

**Why A loses:** it is a view of G-code. `source_command`, missing arc
parameters, tessellating sibling API, no planning lineage, burn/extrude as
peer kinds.

**Why C loses:** it *is* G-code. `MoveType` wire values, modal `None` axes,
F-word, Marlin `e`, dialect on the program envelope, no planning lineage.

**What this does not authorize:** a production `cam_creation_studio.toolpath`
package (that is CS-016), any contour/pocket/drill algorithm, or any change
to preview/G-code runtime behavior.

Working hypotheses that this comparison **does not disprove** (Commit 5 will
enact them unless later evidence contradicts):

* planner owns explicit cutter-center geometry;
* binding ID retained on `ToolpathPlan`;
* drilling expands into travel/plunge/peck/retract motions under a strategy
  object — no canned-cycle type;
* strategy owns depth decomposition (`target_depth_mm` unchanged);
* paths are persistable with fingerprint/staleness;
* laser burn / Marlin extrusion stay off the canonical CNC kind set.

---

## Disposition of existing types (required ruling)

| Existing type | Disposition vs canonical motion |
|---|---|
| Preview `ToolpathSegment` | **Projected into** from B. **Rejected** as storage. Not wrapped. |
| Preview `Segment` | Legacy view. Not reused. |
| G-code `Move` | **Translation target** of a future semantic adapter. **Rejected** as storage. Not wrapped. |
| G-code `ArcMove` | Same as `Move`. |
| `MoveType` | G-code enum. Not reused on B. |
| Imported `Arc2D` / `Line2D` / … | Source geometry. Referenced by id. Not stored as motions. |
| Browser `state.moves` / `manualSegs` | Legacy prototype / UI view. Not authoritative. |

Dependency direction the study prototype must demonstrate:

```text
StudyToolpathPlan
     ├── LinearMotion
     └── ArcMotion
             │
             ▼
      preview adapter
             │
             ▼
     ToolpathSegment
```

Not: plan stores `ToolpathSegment`. Not: plan stores `Move`/`ArcMove`.

G-code side: a **mapping table** is sufficient evidence. Instantiating
`Move`/`ArcMove` is unnecessary unless a static inventory question remains
unanswered (none does).
