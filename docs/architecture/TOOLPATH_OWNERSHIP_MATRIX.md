# Toolpath Ownership Matrix

**Order:** CS-015 (Commit 4)
**Status:** Closed for CS-015. No relevant TBD remains.
**Depends on:** [`TOOLPATH_CURRENT_STATE.md`](TOOLPATH_CURRENT_STATE.md),
[`TOOLPATH_CONTRACT_CANDIDATES.md`](TOOLPATH_CONTRACT_CANDIDATES.md),
study probe `tools/studies/toolpath_contract_probe.py`.

This matrix assigns **one owner** to every responsibility that would otherwise
split across geometry, operations, preview, and G-code. Duplicate ownership is
a defect. “Future” means CS-016+ implements it; CS-015 still names the owner.

Evidence did not disprove the working hypotheses from the CS-015 handoff.

---

## Governing split

```text
source geometry          →  geometry (immutable)
selection / intent       →  workspace
operation semantics      →  operations (definition)
tool / material          →  operations (binding) + feeds_speeds catalogs
advisory recommendation  →  operations (CS-014 wrapper) + feeds_speeds calculator
toolpath strategy        →  toolpath (new; CS-016)
generated path           →  toolpath (canonical ToolpathPlan)
preview                  →  preview (projection of canonical motion)
G-code translation       →  gcode semantic adapter (future) then models.Move
dialect / formatting     →  gcode.dialects + formatter
machine execution        →  operator (never the planner)
```

```text
geometry ≠ toolpath
operation definition ≠ toolpath strategy
target depth ≠ stepdown
feed recommendation ≠ execution authority
toolpath ≠ preview
toolpath ≠ G-code
toolpath planner ≠ controller post
```

---

## Matrix

| Responsibility | Owner | Not the owner | Why |
|---|---|---|---|
| **Source geometry** | `geometry` (`GeometryCollection`, `Line2D`, `Arc2D`, …) | toolpath, preview, G-code | Immutable evidence. Toolpaths **reference** entity IDs. D2. |
| **Selection** | `workspace` (`GeometrySelection`) | toolpath | Membership and order of geometry IDs. Toolpath copies IDs for lineage, not points. |
| **Operation semantics** | `operations` (`OperationDefinition`) | toolpath strategy | Kind, `target_depth_mm`, declarative `ContourRelation` / `CutDirection`, allowances, drill peck/retract **intent**. No generated motion. |
| **Tool / material** | `operations.OperationBinding` + catalog `Tool` / `Material` | toolpath, recommendation payload copies | IDs on the binding; canonical objects stay in `feeds_speeds`. Toolpath stores `binding_id`. |
| **Advisory recommendation** | `OperationFeedRecommendation` wrapping `FeedRecommendation` | toolpath planned feed, G-code F-word | CS-014 advice. May **inform** planned feed. Never execution authority. |
| **Toolpath strategy** | future `ToolpathStrategy` (toolpath package) | `OperationDefinition`, `FeedRecommendation` | DOC, WOC, stepdown, stepover, entry, leads, tabs, compensation policy, climb application, drill expansion, travel height. D13: strategy ≠ generated motion. |
| **Cutter compensation** | **Planner** (toolpath strategy → explicit cutter-center geometry) | G-code G41/G42, controller, `ContourRelation` as geometry | Probe: ON offset 0, INSIDE −R, OUTSIDE +R, applied before motion generation. Symbolic compensation does not survive as the canonical path. Controller compensation is rejected: it would make cutter location dialect-dependent. |
| **Inside/outside resolution** | Toolpath strategy consuming `ContourRelation` | definition (declarative only), geometry winding rewrite | Definition states intent. Strategy produces offset cutter-center path. Source geometry is not mutated. |
| **Climb / conventional** | Toolpath strategy consuming `CutDirection` | geometry importer, G-code | May reverse generated path relative to source winding. Does not rewrite `Arc2D` / polyline vertices. |
| **Depth decomposition** | Toolpath strategy | `target_depth_mm` | Final depth stays on the definition (D3). Strategy emits pass levels (probe: 12 / stepdown 3 → 3, 6, 9, 12). |
| **Stepdown** | Toolpath strategy | CS-012, CS-014 | Not DOC on the definition; not inferred from `target_depth_mm`. |
| **Stepover / WOC** | Toolpath strategy | CS-014 calculator inputs | CS-014 must not grow WOC. Pocket/slot engagement is a strategy parameter. |
| **DOC (per-pass)** | Toolpath strategy | `target_depth_mm` | Per-pass axial engagement. Final depth ≠ DOC. |
| **Entry strategy** | Toolpath strategy | G-code, definition | Plunge, ramp, helix — as **generated motions**, not canned cycles. |
| **Lead-in / lead-out** | Toolpath strategy | G-code | Extra motions on the generated path. |
| **Tabs** | Toolpath strategy | geometry, G-code | Interruptions in generated cut motions. Not source geometry. |
| **Drilling strategy** | Toolpath strategy | G81/G83, `DrillDefinition` as motion | Definition keeps peck/retract **intent**. Strategy **expands** travel/plunge/peck/retract motions. No canned-cycle type. |
| **Generated path** | `ToolpathPlan` / `OperationPath` / `LinearMotion` / `ArcMotion` | preview, G-code, geometry, operations aggregates | Canonical motion. D1: not stored inside geometry, workspace, definition, binding, or recommendation. |
| **Motion kind** | Canonical motion (`travel` / `cut` / `plunge` / `retract`) | G0/G1, Z-sign heuristics | Kind is explicit. Geometry alone does not distinguish plunge from retract. |
| **Analytic arcs** | Canonical `ArcMotion` | tessellated preview, G2/G3 I/J storage | Center, radius, clockwise, sweep. Tessellation is a view (`interpolate_arc`). |
| **Planned path feed** | `ToolpathPlan.planned_feed_mm_min` (and optional per-motion override) | `FeedRecommendation.feed_rate`, F-word | Distinct from recommended feed. |
| **Recommendation provenance** | `ToolpathPlan.recommendation_id` | copying calculator numbers only | ID + planned feed (hypothesis confirmed: neither ID-only nor feed-only suffices). |
| **Path validation** | future toolpath validation (after CS-016) | export preflight, advisory G-code validator | Different question: planned-path consistency vs G-code well-formedness. |
| **Preview** | `preview` as **projection** of canonical motion (today: of G-code) | canonical storage | `ToolpathSegment` is a view. Projection loss is documented, not a reason to weaken the canonical model. D16: no production preview rewrite in CS-015. |
| **G-code translation** | future semantic adapter `toolpath → Move/ArcMove` | contour/pocket planners, preview | Planners do not emit G-code text. `Move`/`ArcMove` remain translation types. |
| **Dialect** | `gcode.dialects` | toolpath | D6. Machine id, arc support, header/footer extras. |
| **G-code formatting** | `gcode.words` / `formatter` | toolpath | Words, comments, rounding. |
| **Machine execution** | Operator | every software layer | D14. No `safe` / `approved` / `machine_ready` fields. |
| **Browser / JS move lists** | Legacy prototype / UI | Python core contract | Inventoried; not authoritative. Later migration may consume Python plans; they do not define them. |
| **Image-etch polylines** | `image` → G-code/preview spur | manufacturing `ToolpathPlan` | Laser/engrave raster paths are not CNC planned motion kinds. |
| **Laser burn / Marlin extrude** | preview / G-code families | canonical CNC kinds | Remain classification of G-code-derived views, not `MotionKind`. |

---

## Feed triad (do not collapse)

```text
recommended feed   CS-014 OperationFeedRecommendation / FeedRecommendation
planned path feed  ToolpathPlan.planned_feed_mm_min
execution feed     operator / later G-code F-word — not a planning authority
```

```text
recommended feed ≠ validated execution feed
recommended feed ≠ planned path feed
```

A planner may initialize planned feed from a current recommendation. That copy
is a planning decision and must keep `recommendation_id`. A stale
recommendation does not silently rewrite planned feed (same no-cascade
doctrine as CS-014).

---

## Depth triad (do not collapse)

```text
target_depth_mm    OperationDefinition — final intended depth
stepdown / DOC     ToolpathStrategy — how to get there
actual Z motion    LinearMotion / ArcMotion coordinates + kind
```

Pass list example (probe): `target_depth_mm = 12`, `stepdown_mm = 3` →
generated levels `3, 6, 9, 12` as `OperationPath.depth_mm`. The definition
field is untouched.

---

## Compensation ruling

Evaluated options:

1. **Planner resolves explicit offsets** — **selected.** Cutter-center
   geometry is known in millimetres, previewable, and translatable without
   G41/G42.
2. Symbolic compensation survives downstream — rejected. Canonical path
   would not be actual cutter location; preview and validation would lie.
3. G-code/controller performs compensation — rejected. Violates D5/D6;
   cutter location becomes dialect- and controller-dependent.

Evidence: `ContourRelation` is already documented as declarative with no
offset computed. The study probe records offset *ownership* without
implementing polygon offset (non-goal).

---

## Conceptual CS-016 interfaces (not implemented)

```python
build_toolpath_plan(operation_plan, definition_id, strategy) -> ToolpathPlan

toolpath_to_preview(toolpath_plan) -> list[ToolpathSegment]   # projection

# Downstream of CS-016, not this study:
toolpath_to_gcode_program(toolpath_plan, dialect_context) -> GCodeProgram
```

`dialect_context` is a G-code-layer input. It must not appear on
`ToolpathPlan`.

---

## CS-016 vs later planners

| Order | Owns |
|---|---|
| **CS-016** | Canonical dataclasses, IDs, lineage, serialization, fingerprint/staleness, preview projection |
| **CS-017+** | Contour / drill / slot / pocket **algorithms** that *fill* `ToolpathPlan` from strategy + geometry |
| **Later** | Path validation, semantic G-code adapter |

CS-016 must not implement machining algorithms. CS-017+ must not invent a
second motion type.
