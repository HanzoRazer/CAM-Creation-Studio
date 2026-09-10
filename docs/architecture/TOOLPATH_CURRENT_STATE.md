# Toolpath Current State — Motion Authority Inventory

**Order:** CS-015 (Commit 1)
**Status:** Evidence inventory only. This document does **not** select a canonical
toolpath contract. Candidate comparison is
[`TOOLPATH_CONTRACT_CANDIDATES.md`](TOOLPATH_CONTRACT_CANDIDATES.md) (Commit 2).
Canonical selection is [`TOOLPATH_CONTRACT.md`](TOOLPATH_CONTRACT.md) (Commit 5).
**Surveyed revision:** `ceeefba` (`origin/main` after merged PR #28 and PR #29).
**Scope:** every current object or function that represents physical motion or
path geometry, plus adjacent types a later reader could mistake for a motion
authority.

```text
Purpose of this file: name what already exists.
Purpose of later CS-015 files: decide what is canonical.
```

CAM-Creation-Studio already has **two Python motion representations** that a
developer could treat as “the toolpath”:

1. Preview `Segment` / `ToolpathSegment` (`cam_creation_studio.preview`).
2. G-code `Move` / `ArcMove` (`cam_creation_studio.models`).

There is **no** production controller-neutral planned-motion type
(`ToolpathPlan`, `OperationPath`, `LinearMotion`, `ArcMotion`, or equivalent).
Manufacturing planning currently ends at `OperationFeedRecommendation` (CS-014).

The browser prototype (`app/`, `src/`) also authors G-code moves and draws
preview polylines. Those surfaces are inventoried in a separate section so they
cannot later be mistaken for a third core authority. They are **not**
authoritative for the Python product core.

---

## Classification vocabulary

Python-core types are classified as exactly one of:

| Class | Meaning |
|---|---|
| **CANONICAL CANDIDATE** | Could, on paper, become the production planned-motion contract. Must be compared in Commit 2. |
| **VIEW PROJECTION** | A rendering, summary, or flattened view of motion. Must not become the production contract by accident. |
| **TRANSLATION MODEL** | A G-code-domain or dialect-adjacent representation used to emit or parse controller text. |
| **LEGACY** | Compatibility / prototype-shaped surface still in the Python core. |
| **UNRELATED** | Path-like geometry or planning state that is **not** generated cutter motion. |

Browser / JS types use a separate vocabulary (see
[Browser / Legacy Prototype Motion Surfaces](#browser--legacy-prototype-motion-surfaces)):

```text
LEGACY PROTOTYPE
UI/VIEW CONCERN
SUPERSEDED EXPERIMENT
NOT AUTHORITATIVE FOR PYTHON CORE
```

A type may be a **CANONICAL CANDIDATE** without being a good one. Candidate
status here means “must be evaluated,” not “should win.”

---

## Inventory summary (Python core)

| Type / function | Path | Class | Why it is here |
|---|---|---|---|
| `ToolpathSegment` | `python/cam_creation_studio/preview/toolpath_model.py` | CANONICAL CANDIDATE (A) | Named “canonical” by CS-003; stores travel/cut/arc/burn/extrude with endpoints and `source_command` G-words |
| `Segment` | same | VIEW PROJECTION / LEGACY | Minimal from/to preview pair; `model_from_moves` tessellates arcs into these |
| `build_toolpath_model` | same | VIEW PROJECTION | G-code → `ToolpathSegment` list |
| `model_from_moves` | same | VIEW PROJECTION | Manual-move dicts → tessellated `Segment`s |
| `model_from_etch_paths` | same | VIEW PROJECTION | Etch polylines → travel/cut/burn `Segment`s |
| `Move` | `python/cam_creation_studio/models.py` | CANONICAL CANDIDATE (C) | Linear/rapid G-code instruction (`MoveType` = `G0`/`G1`) |
| `ArcMove` | same | CANONICAL CANDIDATE (C) | Circular G-code instruction (`G2`/`G3`, I/J or R) |
| `GCodeProgram` | same | TRANSLATION MODEL | Header + ordered `Move`/`ArcMove` + footer |
| `MoveType` | `python/cam_creation_studio/enums.py` | TRANSLATION MODEL | Enum whose values **are** G-words |
| `ParsedLine` | `python/cam_creation_studio/gcode/parser.py` | TRANSLATION MODEL | Lexical G-code line; `.motion` is `'G0'`…`'G3'` |
| `move_from_line` / `parse_moves` | same | TRANSLATION MODEL | Lift text into `Move`/`ArcMove` |
| `Word` / `Line` | `python/cam_creation_studio/gcode/words.py` | TRANSLATION MODEL | Formatter atoms for G-code text |
| `body_lines_from_moves` | `python/cam_creation_studio/gcode/body.py` | TRANSLATION MODEL | `Move`/`ArcMove` → `Line` |
| `build_manual_body` / `build_etch_body` | same | LEGACY / TRANSLATION MODEL | Dict adapters that emit G-code strings |
| `program_to_text` / `build_program` | `python/cam_creation_studio/gcode/generator.py` | TRANSLATION MODEL | Orchestrate header/body/footer text |
| etch `{'poly': …}` dicts | `image/raster_etch.py`, `image/outline_etch.py` | LEGACY (etch path, not CNC plan) | Generated 2D polylines for image burn/engrave |
| `Line2D` / `Arc2D` / `Circle2D` / `Polyline2D` / `Spline2D` | `python/cam_creation_studio/geometry/models.py` | UNRELATED | Imported CAD; no travel/cut, no cutter center |
| `GeometryCollection` | same | UNRELATED | Ordered imported entities |
| `GeometryWorkspace` / `GeometryRef` / `OperationIntent` | `python/cam_creation_studio/workspace/models.py` | UNRELATED | Planning identity; explicitly not a toolpath |
| `OperationDefinition` family | `python/cam_creation_studio/operations/models.py` | UNRELATED | Final intent (incl. `target_depth_mm`); not motion |
| `OperationBinding` | same | UNRELATED | Tool/material IDs |
| `OperationFeedRecommendation` | same | UNRELATED | Advisory CS-014 evidence |
| `FeedRecommendation` | `python/cam_creation_studio/feeds_speeds/calculator.py` | UNRELATED | Advisory numbers, not path |
| `Point` / `Bounds` | `python/cam_creation_studio/shared/geometry.py` | UNRELATED | Shared primitives |
| `interpolate_arc` / `arc_points` | same | VIEW helper | Tessellates G2/G3-style I/J arcs for rendering |
| `Handoff` | `python/cam_creation_studio/handoff/handoff.py` | UNRELATED | Advisory rpm/feed payload |
| validator / preflight | `gcode/validator/`, `safety/preflight.py` | UNRELATED (consumers) | Reason about G-code text; do not own motion |
| CLI `preview` / `parse` summaries | `python/cam_creation_studio/cli/commands/preview.py` | VIEW PROJECTION | Counts/distances over `ToolpathSegment` |

**Gap (must not be papered over):** no type in this table is a controller-neutral
*planned* cutter path derived from `OperationPlan`. That layer does not exist
yet. It is Candidate B, to be compared and (later) defined — not invented in
this inventory.

---

## Detailed Python entries

Each entry records the fields CS-015 Commit 1 requires: path, role, owner,
inputs, outputs, controller coupling, arc fidelity, Z capability, lineage,
persistence, suitability as canonical manufacturing motion.

### 1. `ToolpathSegment` — Candidate A

| Field | Evidence |
|---|---|
| **Path** | `python/cam_creation_studio/preview/toolpath_model.py` |
| **Role** | CS-003 “canonical” preview segment. Docstring: renderer-agnostic motion for a future renderer, report, or inspector. Package docstring still calls this “the canonical shape.” |
| **Owner** | `cam_creation_studio.preview` |
| **Inputs** | Parsed G-code (`str` / `GCodeProgram` / move dicts / `ParsedLine` / `Move`/`ArcMove`) via `build_toolpath_model` |
| **Outputs** | Frozen dataclass: `type` (`travel`/`cut`/`extrude`/`arc`/`burn`), `start`/`end` (preview-local `Point`), `feed`, `z` (end Z), `line`, `source_command`, `distance` |
| **Controller coupling** | **Present.** `source_command` is the originating G-word (`'G0'`…`'G3'`). Classification keys off G0 vs G1 vs G2/G3 and optional E-word / laser dialect. |
| **Arc fidelity** | `build_toolpath_model` keeps an arc as **one** `ToolpathSegment` of `type='arc'` (endpoints + distance). It does **not** store center, radius, sweep, or CW/CCW as first-class fields — direction is only recoverable from `source_command` (`G2`/`G3`). `model_from_moves` **tessellates** G2/G3 into ~40 linear `Segment`s and **drops** analytic form. |
| **Z capability** | Endpoints carry `z`; `ToolpathSegment.z` duplicates `end.z`. No distinction among plunge, retract, stepdown, or `target_depth_mm`. Travel vs cut is a string `type`, not a geometric predicate. |
| **Lineage** | `line` / `source_line` index into the **G-code program**, not `OperationDefinition`, `GeometryRef`, or binding. No operation or geometry IDs. |
| **Persistence** | In-memory list. No document version, fingerprint, or staleness. |
| **Suitability as canonical planned motion** | Weak. It is a **view of already-authored G-code**. It carries G-words, cannot reconstruct an analytic arc from its own fields, has no planning lineage, and its own module tessellates arcs on the older entry point. Naming it `ToolpathSegment` does not make it a manufacturing-planning contract. D9 of CS-015 forbids presuming it canonical. |

### 2. `Segment` — legacy preview pair

| Field | Evidence |
|---|---|
| **Path** | `python/cam_creation_studio/preview/toolpath_model.py` |
| **Role** | Minimal `type`/`frm`/`to`/`feed`/`source_line` pair. `ToolpathSegment` mirrors `frm`/`to`/`source_line` so consumers can treat both as endpoints. |
| **Owner** | `preview` |
| **Inputs** | `model_from_moves`, `model_from_etch_paths` |
| **Outputs** | Linear segments only (arcs flattened) |
| **Controller coupling** | Indirect: G0→`travel`, G1/G2/G3→`cut` or `burn` |
| **Arc fidelity** | Destroyed (tessellation) |
| **Z capability** | `Point.z` on endpoints |
| **Lineage** | Source move index only |
| **Persistence** | None |
| **Class** | VIEW PROJECTION / LEGACY |
| **Suitability** | Not a candidate. Strictly poorer than `ToolpathSegment`. |

### 3. Preview builders and CLI summary

| Symbol | Class | Notes |
|---|---|---|
| `build_toolpath_model` | VIEW PROJECTION | Documented “canonical bridge: parsed program → ToolpathSegment list.” Input is G-code-shaped. |
| `model_from_moves` | VIEW PROJECTION | Flattens arcs; laser flag reclassifies feed as `burn`. |
| `model_from_etch_paths` | VIEW PROJECTION | Z is hardcoded `0.0`; travel connectors between paths. |
| `infer_burn_mode_from_text` | VIEW helper | Comment heuristic; does not own motion. |
| `bounds(segments)` | VIEW helper | XY box of endpoints. |
| `summarize_segments` (`cli/commands/preview.py`) | VIEW PROJECTION | Counts and distances. `camstudio preview` / `camstudio parse` consume G-code text, never an `OperationPlan`. |

Preview `Point` in this module is a **second** `Point` type (x, y, z=0), not
`cam_creation_studio.shared.geometry.Point`. That duplication is a preview
implementation detail, not a third motion authority.

### 4. `Move` / `ArcMove` — Candidate C

| Field | Evidence |
|---|---|
| **Path** | `python/cam_creation_studio/models.py` |
| **Role** | Domain vocabulary for **one G-code motion instruction**. `Move` = linear/rapid; `ArcMove` = circular. Together they are the body of `GCodeProgram`. |
| **Owner** | G-code domain (`models` + `gcode`) |
| **Inputs** | Generator (`program_from_config`), parser (`move_from_line` / `move_from_dict`), tests, CLI generate |
| **Outputs** | Frozen slots dataclasses consumed by `body_lines_from_moves` → `Line` → text |
| **Controller coupling** | **Structural.** `Move.type` / `ArcMove.type` is `MoveType`, whose values are `"G0"`, `"G1"`, `"G2"`, `"G3"`. `feed` is the F-word. `e` is Marlin extrusion. Unset axes are `None` to preserve **G-code modality**. `comment` is a G-code comment. |
| **Arc fidelity** | Analytic **in G-code form**: I/J offsets from start, or R (negative R = major arc, G-code convention). No explicit center point, no stored sweep, no plane tag. Clockwise vs CCW is `MoveType.ARC_CW` / `ARC_CCW` (G2/G3). |
| **Z capability** | Optional `z` word. Modal: omitted Z means “controller keeps last Z,” which is a **G-code** rule, not a planned absolute pose. No plunge/retract kind. |
| **Lineage** | None to geometry or operations. Optional `comment` string only. |
| **Persistence** | `GCodeProgram.to_json` / `from_json` via `move_from_dict`. This persists a **program**, not a planning document. No staleness vs `OperationPlan`. |
| **Suitability as canonical planned motion** | Weak for CS-015’s purpose. D5/D6 forbid G-words and dialect identity on the toolpath contract. D10 forbids presuming this model canonical. Modal `None` axes are the opposite of explicit cutter-center poses. Marlin `e` is not a CNC manufacturing motion kind. |

`GCodeProgram` is the envelope (header/footer + moves). Header/footer carry
`machine` dialect strings (`genericCnc`, `marlin`, …), `safe_z`, spindle flags,
and M-code `end_code`. That envelope is a **translation / program** object, not
a planned toolpath.

### 5. `MoveType`

| Field | Evidence |
|---|---|
| **Path** | `python/cam_creation_studio/enums.py` |
| **Role** | Closed set of motion commands “the core understands.” |
| **Values** | `RAPID = "G0"`, `LINEAR = "G1"`, `ARC_CW = "G2"`, `ARC_CCW = "G3"` |
| **Class** | TRANSLATION MODEL |
| **Suitability** | Unusable as a controller-neutral vocabulary. The wire values **are** G-code. `is_cut` treats everything except rapid as a cut, including arcs — a G-code heuristic, not a planning kind. |

### 6. Parser, words, generator, body

These are the G-code pipeline around Candidate C. They do not introduce a
separate motion geometry; they translate `Move`/`ArcMove` to and from text.

| Symbol | Path | Class | Coupling |
|---|---|---|---|
| `ParsedLine` | `gcode/parser.py` | TRANSLATION MODEL | `.motion` returns `'G0'`…`'G3'`; `.gword` / `.mword` |
| `move_from_line` | same | TRANSLATION MODEL | No modal feed carry-over (documented round-trip choice) |
| `parse_program_model` | same | TRANSLATION MODEL | Infers header/footer; dialect not encoded in text |
| `Word`, `Line` | `gcode/words.py` | TRANSLATION MODEL | Command strings such as `'G1'`, `'M3'` |
| `body_lines_from_moves` | `gcode/body.py` | TRANSLATION MODEL | Emits I/J for arcs; E for Marlin |
| `build_manual_body` | same | LEGACY adapter | Dict `{type,x,y,z,f,e,i,j}` → G-code strings |
| `build_etch_body` | same | LEGACY / TRANSLATION | Etch polylines → G0/G1 **and** M3/M5 |
| `program_to_text`, `build_program` | `gcode/generator.py` | TRANSLATION MODEL | Header/body/footer orchestration |
| `header_lines` / `footer_lines` | `gcode/header.py`, `footer.py` | TRANSLATION MODEL | Safe-Z **G0**, dialect extras, park |
| `Dialect` | `gcode/dialects.py` | TRANSLATION MODEL | `supportsArcs`, machine id (`marlin`, `genericCnc`, `laserGrbl`) |

**Arc note:** `build_etch_body` never emits G2/G3. Image etch is polyline-only.

**Z note:** header emits a rapid to `safeZ`; etch depth mode plunges to
`engraveZ` and retracts to safe Z — as **G-code text**, not as planned motion
kinds.

### 7. Image-etch path dicts

| Field | Evidence |
|---|---|
| **Path** | `python/cam_creation_studio/image/raster_etch.py`, `outline_etch.py`, `marching_squares.py` |
| **Role** | Generate 2D polylines from a `DarknessField` for laser/engrave jobs. Output: `{'poly': [{'x','y'}, ...]}` in millimetres. |
| **Owner** | `cam_creation_studio.image` |
| **Class** | LEGACY relative to manufacturing planning; **etch-specific generated path**, not an `OperationPlan` consumer |
| **Controller coupling** | None in the polyline itself. Coupling appears when `build_etch_body` / `model_from_etch_paths` consume it. |
| **Arc fidelity** | None (chords / scan lines). Marching-squares outlines are piecewise linear by construction. |
| **Z capability** | None on the polyline; Z is applied later by etch control (`power` vs `depth`). |
| **Lineage** | No geometry-entity or operation IDs. Pixel-derived. |
| **Persistence** | Ephemeral list of dicts. |
| **Suitability** | Not a CNC manufacturing-motion candidate. CS-015 working hypothesis: laser burn / Marlin extrusion are **not** canonical CNC motion kinds. These paths remain an image-etch pipeline into G-code/preview. They must still be inventoried so they are not later “discovered” as a third toolpath type. |

`DarknessField` is a raster sampling grid, not motion. Class: UNRELATED.

### 8. Neutral imported geometry

| Type | Path | Class | Why not motion |
|---|---|---|---|
| `Line2D` | `geometry/models.py` | UNRELATED | Source CAD segment. No travel/cut, no feed, no operation. |
| `Arc2D` | same | UNRELATED | Analytic **source** arc: center, radius, start/end angle (degrees, **CCW DXF convention**). Not cutter-center motion; no CW/CCW travel kind; Z is whatever the imported point carries. |
| `Circle2D` | same | UNRELATED | Full circle as geometry, not a helical or contour path. |
| `Polyline2D` | same | UNRELATED | Vertex chain; bulges already flattened at import (`POLYLINE_BULGE_IGNORED`). |
| `Spline2D` | same | UNRELATED | Control/fit evidence; not tessellated into motion here. |
| `GeometryCollection` | same | UNRELATED | Source-ordered bag + diagnostics. Immutable; CS-015 D2: toolpaths reference it, they do not mutate it. |
| `SourceReference` | same | UNRELATED | DXF provenance. |

`geometry/bounds.py` `arc_extent` computes a bounding box for a CCW arc. That is
geometry math, not a motion type. Class: UNRELATED utility.

**Arc-convention collision (inventory fact, not a decision):** imported `Arc2D`
is DXF-CCW in degrees; G-code `ArcMove` is G2/G3 with I/J or signed R;
preview tessellation uses G2=clockwise signed sweep. Any future canonical arc
must pick one planning convention and treat the others as projections.

### 9. Workspace and operations (planning, not path)

These are **upstream of** CS-015. They are inventoried so “toolpath-shaped”
fields are not hidden inside them.

| Type | Path | Motion-like fields | Class |
|---|---|---|---|
| `GeometryRef` | `workspace/models.py` | Identity of imported entity | UNRELATED (lineage source) |
| `GeometrySelection` | same | Ordered entity IDs | UNRELATED |
| `OperationIntent` | same | `kind` only (`contour`/`pocket`/`drill`/…) | UNRELATED |
| `GeometryWorkspace` | same | Holds geometry by reference | UNRELATED |
| `ContourDefinition` etc. | `operations/models.py` | `target_depth_mm`, `relation`, `direction`, allowances, drill `peck_depth_mm` / `retract_height_mm` | UNRELATED (intent, not generated levels) |
| `OperationBinding` | same | `tool_id`, `material_id` | UNRELATED (lineage source) |
| `OperationFeedRecommendation` | same | wraps `FeedRecommendation` + `input_fingerprint` | UNRELATED (advisory evidence) |
| `OperationPlan` | `operations/plan.py` | Aggregate document | UNRELATED |

Documented non-ownership (must remain true):

* `ContourRelation` / `CutDirection` are **declarative**. No offset, winding, or
  path is computed (`operations/enums.py`).
* `target_depth_mm` is **final intended depth**, not DOC or stepdown
  (`operations/models.py`, CS-012).
* Drill peck/retract are **planning intent only**. “No canned-cycle generation.”
* CS-014 recommendations are advisory; they do not generate motion.

### 10. Shared geometry helpers

| Symbol | Path | Class |
|---|---|---|
| `Point`, `Bounds` | `shared/geometry.py` | UNRELATED primitives (mm by convention) |
| `distance`, `distance_2d`, `arc_length` | same | UNRELATED math |
| `interpolate_arc` / `arc_points` | same | VIEW helper — flattens I/J arcs for rendering; docstring says “G2/G3” |
| `stable_id` / `new_id` | `shared/ids.py` | UNRELATED — ID strategy CS-016 can reuse; not a motion type |

`interpolate_arc` is the shared tessellator. Canonical planned motion must **not**
treat its output as storage. Preview and future renderers may call it.

### 11. Feeds, handoff, validation, preflight

| Symbol | Class | Why listed |
|---|---|---|
| `FeedRecommendation` | UNRELATED | Advisory rpm/feed/chipload. May later **inform** planned path feed; it is not a path. |
| `Handoff` | UNRELATED | `{rpm, feed, units, material}` applied onto **G-code job configs**, not onto planned motion. |
| `validate_program` / safety rules | Consumer of G-code | `CUT_WITHOUT_FEED`, `ARC_WITHOUT_CENTER_OR_RADIUS` inspect `ParsedLine` motion. They do not define a toolpath type. |
| `run_export_preflight` | Consumer of G-code text | Export gate. Not a motion model. |

### 12. Preview-local vs shared `Point`

Two `Point` types exist:

* `cam_creation_studio.shared.geometry.Point` — canonical primitive.
* `cam_creation_studio.preview.toolpath_model.Point` — preview-only duplicate.

This is a representation split inside preview, not a third motion authority.
Noted so CS-016 does not inherit the duplicate as “the toolpath point.”

---

## Browser / Legacy Prototype Motion Surfaces

CAM-Creation-Studio’s Python core is the architectural target
(`docs/architecture.md`). The product passed through an HTML/browser prototype.
Those surfaces still contain move lists and preview polylines. Leaving them
unnamed would recreate the “third authority discovered later” failure CS-015
exists to prevent.

**Rule used:** inventory a JS/HTML surface only if a future developer could
plausibly treat it as another toolpath contract. No JS modifications are
authorized by this inventory. No comprehensive JavaScript archaeology.

**Product-core statement (inventory fact; ratification is Commit 5 / merge):**

```text
Existing browser-side motion/path objects are consumers, adapters,
legacy prototypes, or candidates for later migration; they do not
define the core motion contract.
```

The Python controller-neutral contract (to be selected later in CS-015 and
implemented in CS-016) is the authority for the product core.

### Summary (browser / archive)

| Surface | Path | Classification | Could it be mistaken for a core toolpath? |
|---|---|---|---|
| Manual move list in UI state | `app/main.js` (`state.moves`) | LEGACY PROTOTYPE | **Yes** — same `{type: 'G0'\|'G1'\|'G2'\|'G3', x,y,z,f,e,i,j}` shape as Python dict adapters |
| Canvas preview segments | `app/main.js` `draw()` `manualSegs` | UI/VIEW CONCERN | **Yes** — `{kind: 'rapid'\|'cut', poly, z}`; arcs tessellated to 40 points |
| Etch polyline cache | `app/main.js` `generateEtch` / `etchCache` | UI/VIEW CONCERN | Weak — image paths, not operation planning |
| JS G-code generator | `src/gcode/generator.js` | LEGACY PROTOTYPE; NOT AUTHORITATIVE FOR PYTHON CORE | **Yes** — parallel `buildManualBody` / `buildEtchBody` / `buildProgram` |
| JS formatter / dialects | `src/gcode/formatter.js`, `dialects.js` | LEGACY PROTOTYPE | Indirect (emits G-words; `supportsArcs`) |
| JS handoff | `src/handoff/handoff.js` | NOT AUTHORITATIVE FOR PYTHON CORE | No (advisory rpm/feed only); listed because `isCutMove` keys off G1/G2/G3 |
| JS unit tests | `tests/gcode-generator.test.js`, `tests/handoff.test.js` | LEGACY PROTOTYPE tests | They lock **JS** generator behavior, not Python planned motion |
| Original DC HTML apps | `archive/original-html/G-code Creator.dc*.html` | SUPERSEDED EXPERIMENT | **Yes** if read as current architecture — inlined move tables + canvas tessellation |
| Tutorial HTML | `archive/original-html/G-code Quick-Start Manual.dc.html` | SUPERSEDED EXPERIMENT | Educational G0/G1 text; not a data model |
| `src/preview` | *(does not exist)* | — | `app/main.js` comment: “slated for extraction to src/preview.” There is no extracted preview module. Absence is recorded so nobody searches for a missing third Python-equivalent. |

### Browser details that matter to CS-015

**`app/main.js` moves.** Default state is four dicts with `type` in
`G0`/`G1`/`G2`/`G3` and I/J fields. The UI editor offers those four commands.
This is the same dict contract `python/.../gcode/body.py` `build_manual_body`
and `python/.../preview/toolpath_model.py` `model_from_moves` accept. It is a
**legacy authoring UI** over G-code moves, not a planned `ToolpathPlan`.

**`app/main.js` `draw()`.** For non-etch mode it walks `state.moves`, tessellates
G2/G3 with 40 steps (same N as Python `_ARC_STEPS` / `interpolate_arc` default),
and stores `{ kind: 'rapid'|'cut', poly, z }`. Analytic arcs do not survive.
Z is a per-segment scalar for depth coloring (`depthColor`), not a motion kind.
Class: UI/VIEW CONCERN.

**`src/gcode/generator.js`.** Port of the original app; DOM-free. Emits G-code
strings from move dicts and etch polylines. `buildHeader` emits `G0 Z{safeZ}`.
`buildEtchBody` emits G0/G1 and M3/M5. Python `gcode` is the maintained core;
this file is a behavioral reference (`docs/architecture.md`). Class: LEGACY
PROTOTYPE; NOT AUTHORITATIVE FOR PYTHON CORE.

**Archive HTML.** `G-code Creator.dc.html` (and numbered copies) contain the
same move table and canvas tessellation. Class: SUPERSEDED EXPERIMENT.
Provenance only.

No browser type is a CANONICAL CANDIDATE for the Python core.

---

## Overlapping authorities (the CS-015 problem statement)

Three *stories* currently describe “how the tool moves,” and they do not share
a planned-motion type:

```text
Imported geometry          (what the part looks like)
        ≠
G-code Move / ArcMove      (what a controller program says)
        ≠
Preview Segment / ToolpathSegment
                           (what a renderer/summary sees after G-code)
        ≠
(missing) planned toolpath (what CS-015 must define)
```

Data flow today for “preview a toolpath”:

```text
manual dicts or G-code text
        ↓
Move / ArcMove   (optional typed lift)
        ↓
G-code text
        ↓
build_toolpath_model
        ↓
ToolpathSegment list
        ↓
CLI summary / (future) renderer
```

There is **no** arrow from `OperationPlan` into any of those boxes.

Image etch is a parallel spur:

```text
DarknessField → etch polylines → G-code (build_etch_body)
                               → preview Segments (model_from_etch_paths)
```

Browser UI is a parallel prototype of the first spur, not a consumer of
`OperationPlan`.

---

## Fidelity notes the later study must use

These are facts, not selections.

1. **Analytic arcs already exist in two incompatible forms:** `Arc2D` (DXF
   center/radius/angles) and `ArcMove` (G2/G3 I/J or R). Preview’s richer
   segment keeps endpoints + G-word + length only. `model_from_moves` and
   `app/main.js` destroy analytic form.
2. **G-words are embedded** in `MoveType`, `Move.type`, `ArcMove.type`,
   `ToolpathSegment.source_command`, `ParsedLine.motion`, `Line.command`, and
   every JS move `type`.
3. **Z is a coordinate or a G-word, never a planning kind.** Plunge vs retract
   vs travel height is inferred by humans (or by header/etch templates), not
   modeled.
4. **Lineage to operations/geometry is absent** from all current motion types.
   Preview lineage is source **line numbers**. Geometry lineage is DXF
   `SourceReference`. They do not meet.
5. **Travel vs cut** exists in preview (`travel`/`cut`/`burn`/`extrude`) and in
   G-code (`G0` vs `G1`/`G2`/`G3`). It does not exist on imported geometry.
6. **Drilling** exists only as `DrillDefinition` parameters
   (`peck_depth_mm`, `retract_height_mm`). No expanded plunge/retract motions
   and no canned-cycle objects.
7. **Compensation / climb** exist only as enums on definitions. No cutter-center
   path is computed.
8. **Persistence/staleness** exists for `OperationPlan` recommendations
   (`input_fingerprint`, `RecommendationStatus`). It does not exist for any
   motion list.
9. **Units:** geometry and feeds are millimetres. G-code programs can declare
   inches (`Units.INCH` → G20). Planned motion must not grow a parallel inch
   model (CS-015 D7).

---

## Completeness check

Every Python object that represents physical motion or path geometry in the
product core is listed above. Adjacent types that look like motion (imported
arcs, etch polylines, G-code words, preview summaries) are listed so they cannot
be rediscovered as unnamed authorities.

Browser/archive surfaces that could be mistaken for a contract are listed in
the prototype section. Unrelated planning types are listed to record that they
**do not** already store generated motion (CS-015 D1).

This inventory does **not** choose among Candidates A, B, and C. It establishes
that A and C already exist, that B does not, and that browser motion is not a
fourth Python-core candidate.
