# Toolpath Lineage and Staleness

**Order:** CS-015 (Commit 5)
**Status:** Selected with the canonical contract.
**Companion:** [`TOOLPATH_CONTRACT.md`](TOOLPATH_CONTRACT.md)
**Production:** [`docs/TOOLPATH_CORE.md`](../TOOLPATH_CORE.md) persists
`strategy_fingerprint` and `upstream_fingerprint` (including
`planned_feed_mm_min`) on `ToolpathPlan`.

---

## Persistence decision

**Persisted, fingerprinted, and stale-able.**

Always-derived-only was rejected: generated motion will not be cheap, and
CS-014 already established attributable stored planning evidence with an
`input_fingerprint`. Toolpaths follow that doctrine.

```text
derived on demand     — rejected as the only mode
persisted bare        — rejected (silent staleness)
persisted + fingerprint + status  — selected
```

A stored `ToolpathPlan` is planning evidence. It is not machine-ready.

---

## Upstream identity inputs

These identities must be recoverable from a `ToolpathPlan` without guessing:

| Input | Where it lives on the plan | Source of truth |
|---|---|---|
| Generating operation | `operation_definition_id` (exactly one) | `OperationDefinition.id` |
| Source geometry | `geometry_ids` (ordered; no point copies) | workspace selection → `GeometryRef.id` |
| Binding | `binding_id` | `OperationBinding.id` |
| Advisory feeds | `recommendation_id` (optional) | `OperationFeedRecommendation.id` |
| Planned feed | `planned_feed_mm_min` | toolpath (not the calculator) |
| Strategy | `strategy_fingerprint` | `ToolpathStrategy` computational fields |
| Aggregate inputs | `upstream_fingerprint` | composition of the rows above plus digests |

Per-motion `geometry_ids` may subset the plan-level list when a path traces to
part of a multi-entity selection. Empty per-motion ids mean “inherit plan-level
geometry_ids.” Neither level copies `Line2D` / `Arc2D`.

---

## Lineage requirements

### Operation

Every `ToolpathPlan` has **exactly one** `operation_definition_id`.
One definition may eventually yield several plans (re-strategy); one plan
does not mix definitions.

`REFERENCE` definitions do not generate paths.

### Geometry

Motion must trace to the selection’s `GeometryRef` ids. If the selection has
multiple refs, the plan preserves that tuple. No geometry clone “for
lineage.”

Imported `SourceReference` (DXF handle) stays on the entity. Toolpath does
not duplicate it.

### Binding

`binding_id` is stored on the plan. Walking `OperationPlan.bindings` is a
convenience, not the persistence story.

Tool/material **catalog** changes (diameter, flutes) stale the plan via
digest even if the binding id is unchanged (same as CS-014).

### Recommendation / feed

Both:

* `recommendation_id` — why a number was suggested;
* `planned_feed_mm_min` — what the path actually carries.

A missing recommendation is valid (incomplete planning). Planned feed may
still be set by the operator/strategy.

---

## Fingerprint candidates

Two fingerprints, both deterministic JSON → `stable_id` (no timestamps,
no labels).

### `strategy_fingerprint`

Computational strategy fields only:

* `travel_height_mm`
* `stepdown_mm`, `stepover_mm`
* `peck_depth_mm`, `retract_height_mm`
* later: entry, lead-in/out, tab parameters, compensation policy enum

**Excluded:** `label`, notes, UI names.

### `upstream_fingerprint`

* `geometry_ids`
* `geometry_digest` — hash of referenced entity geometry (kind + mm
  coordinates + closure), not display layer names
* `definition_digest` — type, `target_depth_mm`, relation, direction,
  allowances, drill peck/retract intent
* `binding_id` plus tool/material computational fields (`diameter_mm`,
  `flutes`, material id / chipload range)
* `recommendation_digest` — recommendation id + calculator-driving
  fingerprint if present; `null` if none
* `strategy_fingerprint`
* `planned_feed_mm_min`

**Excluded:** workspace selection **name**, group descriptions, definition
display names, recommendation notes/warnings text, strategy `label`.

The study probe implements this split
(`strategy_fingerprint` vs `upstream_fingerprint` inputs) and proves labels
do not invalidate.

---

## Stale conditions

| Change | Stale? |
|---|---|
| Source geometry coordinates / kind / closure | **Yes** |
| Geometry id set (selection membership) | **Yes** |
| Operation definition computational fields | **Yes** |
| Binding id | **Yes** |
| Tool diameter / flutes or material chipload | **Yes** |
| Recommendation computational identity (or id) | **Yes** if `recommendation_id` is set |
| Strategy computational fields | **Yes** |
| Planned feed | **Yes** |
| Strategy or selection **label/name** | **No** |
| Recommendation notes / advisory wording | **No** |
| Unrelated other operations on the same `OperationPlan` | **No** |

Status vocabulary (parallel to CS-014, names may be reused):

```text
missing   — no stored path for this definition+strategy
current   — upstream_fingerprint matches
stale     — stored path exists; fingerprint does not match
```

`STALE` is structural. It is not `unsafe`. Regeneration is explicit (replace
helper), not a silent cascade when the operator edits a label.

Referential integrity (same doctrine as CS-011–CS-014):

```text
cannot remove a definition / binding / recommendation
while a persisted toolpath still names it
```

Exact error types are CS-016’s to name. No cascade delete.

---

## Document versioning (CS-016)

Follow operation-plan practice: `read ≠ migration`.

* New documents carry an explicit version (`camstudio_toolpath_v1`).
* Unknown versions fail closed.
* Toolpaths are **not** stored inside `OperationPlan` JSON (D1). They are a
  sibling document or a named collection keyed by plan/definition id.

CS-015 does not require shipping the document in this order — only the
rule that when CS-016 persists, it fingerprints.

---

## Why motion exists (the lineage sentence)

A motion exists because:

1. an `OperationDefinition` named a machining intent on a selection;
2. a `ToolpathStrategy` decided how to realize that intent (compensation,
   depth passes, entry, drill expansion);
3. the generator emitted this segment at this pose, with these geometry
   ids, this kind, and this planned feed.

If a stored plan cannot say (1) and (2), it is incomplete. If it can only
say “G1 from a preview,” it is the wrong authority.
