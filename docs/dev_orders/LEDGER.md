# Dev-Order Ledger — CAM-Creation-Studio

**Order:** CS-REC-04 · **Scope:** this repository only.

Every development order accepted by CAM-Creation-Studio is indexed here. The
ledger exists so a misrouted order is detectable **on arrival** rather than
several exchanges later: an order whose *Parent Artifact* cannot be located **in
this repository**, or whose *Repository* is not this one, is treated as misrouted
until confirmed.

Note the test is *locatable in the repository*, not *listed in this ledger*. A new
order may legitimately name an artifact that has no index row yet; requiring a row
would reject valid work and make the ledger a bottleneck rather than a check.

See [`../SESSION_INTEGRITY_2026-08-07.md`](../SESSION_INTEGRITY_2026-08-07.md)
for the incident that motivated this.

---

## Source of truth

This ledger duplicates information that also lives in GitHub. Where they diverge,
the rule is not negotiable:

| Question | Authority |
|---|---|
| Is a PR open, merged, or closed? Which branch exists? | **GitHub.** Always. |
| Which order does a branch belong to; what was ruled and why | **This ledger.** |
| What a finding says | The audit or artifact it names — never a summary of it |

**PR and branch statuses recorded here are descriptive, not authoritative.** They
are a snapshot taken when someone last refreshed them, and they go stale the moment
a PR merges. Treat a status column as a hint about where to look, then confirm
against `gh pr list` / `git branch -r`. A disagreement between this table and
GitHub is a stale ledger, never a stale GitHub.

What the ledger *is* authoritative for is the reasoning GitHub does not record:
which identifiers are retired, why one PR superseded another, and what sequencing
was decided. Those do not expire.

### Keeping it current

- **Refresh on merge.** Whoever merges a PR that appears in § Order index updates
  its row in the same session. A stale row is a governance defect, not cosmetic.
- **Anyone may correct it.** Amending a status to match GitHub is routine
  maintenance and needs no ruling. Changing a *disposition* — canonical vs
  superseded, retired vs live — is an owner decision and must record who decided
  and when, as § Resolved conflicts does.
- **Correcting the ledger is not contradicting policy.** If reality and this file
  disagree, the file is wrong. Fix it and move on.

### Enforcement status

Nothing here is enforced by CI. The provenance header, the rejection rules, and
the pre-PR checks are **process requirements carried out by hand**; no hook,
workflow, or test validates them today. Read "must" as "is required by process and
will be caught by a reviewer, if at all" — not "the system will stop you."
Automating the mechanical parts (header presence, retired-identifier use, link
resolution) is unissued follow-up work.

---

## Mandatory provenance header

Every dev order must open with:

```text
Repository:                CAM-Creation-Studio
Repository Root:           HanzoRazer/CAM-Creation-Studio
Repository Branch:         <branch the order targets>
Parent Artifact:           <repo-relative path to the artifact that authorises this>
Authority:                 <what makes that artifact authoritative>
Generated:                 <YYYY-MM-DD the order was written>
Cross Repository Deps:     <None, or the named repositories>
```

The angle-bracketed fields are placeholders — fill them in per order. Only the
first two are fixed values. An example with every field populated is the header of
any accepted order in § Order index.

**Rejection rules.** An order is misrouted, and must be confirmed before any
work begins, when *Repository* names another product; when *Parent Artifact*
cannot be located in this repository; when the identifier appears in
§ Retired identifiers; or when *Cross Repository Dependencies* names a
repository this session is not rooted in.

---

## Identifier namespaces

| Namespace | Owner | Notes |
|-----------|-------|-------|
| `CS-xxx` | CAM-Creation-Studio | Implementation orders |
| `CS-REC-xx` | CAM-Creation-Studio | Governance / recovery |
| `CAM-Axx` | **CAM-Assist-Blueprint** | **Never valid here** |
| `CAM-CS-xx` | *retired* | Ambiguous; see below |

Namespaces never overlap. **A retired identifier is never reissued.**

### Retired identifiers

Merged history is deliberately **not** renumbered — Git history stays stable and
traceable. Retirement is recorded instead.

| Retired | Used for | Disposition |
|---------|----------|-------------|
| `CAM-CS-01` | Fretboard workflow intake → realigned to authority/boundary study | **Retired as a namespace.** Work merged (`831680f`, ratified `db68f16`); references remain valid historically. |
| `CAM-CS-02` (1st use) | Export Preflight Validation | **Void — misrouted.** Withdrawn by the owner; reissued as `CS-009`. |
| `CAM-CS-02` (2nd use) | Shared Fret-Math Extraction Study | **Retired.** Collides with the above. Successor: `CS-010`, unissued. |

---

## Order index

| ID | Title | Parent artifact | Branch | Status | Superseded by | Constitutional impact |
|----|-------|-----------------|--------|--------|---------------|----------------------|
| CS-002 | Python core architecture | — | — | Merged | — | Established core layout |
| CS-003 | Validation / preview / feeds contracts | — | `cs-003-completion` | Merged (#1) | — | Diagnostic code contract |
| CS-006 | Laser classification parity | — | — | Merged (#4, #5) | — | None |
| CS-007 | CLI foundation | — | `cs-007-cli-foundation` | Merged (#6) | — | Public API extended |
| CS-008 | DXF import & neutral geometry model | — | `cs-008-dxf-import` | Merged (#7) | — | New subsystem |
| CAM-CS-01 | Fretboard intake → authority study | Repository inventory | `cam-cs-01-authority-grounding` | Merged (#8); **ratified** `db68f16` | — | Product boundary; ratified 2026-08-05 |
| CAM-CS-02 *(1st)* | Export preflight | — | — | **Void — misrouted** | CS-009 | — |
| CS-009 | Export preflight gate | `docs/architecture/EXPORT_PREFLIGHT_SEMANTICS.md` | `cs-009-export-preflight` | Merged (#9) | — | Export gate; no machine-readiness claim |
| CS-008R | Geometry import conformance re-audit | — | `cs-008r-conformance-reaudit` | Merged (#12) | — | Evidence only |
| CS-008 REM 1/3 | Import loss evidence + characterization | CS-008R (unseen at the time) | `cs-008-import-evidence` | **Closed — re-scoped** (#10) | **#17** | — (not merged) |
| CS-008 REM 1/3-R | Import loss evidence infrastructure | `docs/audits/CS-008_REAUDIT.md` | `cs-008-loss-evidence` | Merged (#17) `9a967f7` | — | Loss fields, `LOSS_CODES`, `ImportReport`; **diagnostic `metadata` constrained to JSON-safe values, enforced** |
| CS-008 REM 2/3 | Spline fidelity | as above | `cs-008-spline-fidelity` | Merged (#11) `ed66bca` | — | `Spline2D` extended; F2/F3/F4 verified against the audit |
| CS-008 REM 3/3 | Coordinate correctness | as above | `cs-008-coordinate-correctness` | **Closed — superseded** (#13) | **#14** | — (not merged) |
| CS-008R F1 | OCS→WCS on import | `docs/audits/CS-008_REAUDIT.md` | `cs-008-f1-coordinate-correctness` | Merged (#14) `c60009c` | — | Coordinates corrected |
| CS-008R F1-H | Post-F1 OCS hardening | `docs/audits/CS-008_REAUDIT.md` | `cs-008r-ocs-completeness` | Merged (#16) `b9f181f` | — | Diagnostic split: `NON_PLANAR_GEOMETRY` |
| CS-008R-F5F7 | Import evidence completeness | `docs/audits/CS-008_REAUDIT.md` | `cs-008r-import-evidence-completeness` | Merged (#19) `d6c7a8f` | — | Elevation resolved; `SourceReference` provenance; `MISSING_LAYER` given semantics |
| CAM-CS-02 *(2nd)* | Shared fret-math extraction study | CAM-CS-01 audit §7 | — | **Retired identifier; unissued** | CS-010 | Cross-repository |
| CS-REC-01…05 | Session integrity recovery | This ledger | `cs-rec-governance` | Merged (#15) `4cc28a9` | — | Governance only |
| CS-008R-CL | Audit disposition and import closure | `docs/audits/CS-008_REAUDIT.md` | `cs-008r-closure` | Merged (#21) `beb07b6` | — | F8/F9/F10 disposed; vocabulary classified; CS-008R **CLOSED**; importer frozen |
| CS-008R-D1 | Mesh / Polyface Import Fidelity Evidence | `docs/audits/CS-008R_CLOSURE.md` | `cursor/cs-008r-d1-mesh-fidelity-d47b` | Merged (#22) `baa566d` | — | Additive `POLYLINE_MESH_TOPOLOGY_DROPPED`; no mesh model; `has_lossy_import` unchanged |
| CS-011 | Neutral geometry consumer foundation | `docs/GEOMETRY_IMPORT.md` | `cursor/cs-011-neutral-geometry-consumer-d47b` | Merged (#24) `a74c99e` | — | New `workspace` package; planning state only; no toolpath / feeds / G-code |
| CS-012 | Operation definition v1 | `docs/GEOMETRY_WORKSPACE.md` | `cursor/cs-012-operation-definition-5005` | Merged (#26) `29988c7` | — | New `operations` package; planning parameters; no tool / feeds / toolpath / G-code |
| CS-013 | Tool / material binding | `docs/OPERATION_DEFINITION.md` | `cursor/cs-013-tool-material-binding-5005` | Merged (#27) `ac52fe3` | — | `OperationBinding` on `OperationPlan`; canonical Tool/Material IDs; no feeds / machine / toolpath / G-code |
| CS-014 | Feeds / speeds integration | `docs/TOOL_MATERIAL_BINDING.md` | `cursor/cs-014-feeds-speeds-integration-5005` | Open (#28) | — | Attributable advisory `FeedRecommendation`; explicit `spindle_rpm`; no DOC/WOC / toolpath / G-code |

*Status column last refreshed 2026-08-30.* Confirm against GitHub before relying
on it — see § Source of truth.

**No CS-008 order is open.** CS-008R-D1 merged as #22 (`baa566d`). CS-008R-CL
merged as #21. **CS-011** merged as #24 (`a74c99e`). **CS-012** merged as #26
(`29988c7`). **CS-013** merged as #27 (`ac52fe3`). **CS-014** is open as #28.
The importer remains under feature freeze — defects only.

---

## Resolved conflicts

**#13 vs #14 — duplicate F1 remediation.** Two concurrent sessions independently
fixed audit finding F1, both touching `geometry/entities.py` and
`geometry/diagnostics.py`.

**Disposition (owner ruling, 2026-08-07): #14 is canonical.** It branches
directly from `main`, implements F1 in isolation, leaves F2–F7 untouched, and is
mergeable. #13 does not merge: it is stacked behind #10/#11 and mixes F5
(LWPOLYLINE elevation) into F1, violating the requirement that F1 land first and
alone.

- #13 **closed as superseded**; implementation notes and test ideas preserved in
  its closing comment.
- Branch `cs-008-coordinate-correctness` is **retained**, not deleted, until the
  remaining remediation is reconciled.
- **No commit from #13 is cherry-picked onto `main`.**

*Corroboration worth keeping:* both implementations independently derived the
same mirrored-arc rule — `(start, end) → (180 − end, 180 − start)` — and both
correctly leave `LINE` untransformed. Independent agreement on the non-obvious
part raises confidence in #14.

**And its limit, recorded 2026-08-08.** #14 merged, and post-merge review then
found a regression *both* implementations shared: POLYLINE mesh flavours report
`is_3d_polyline` false but store WCS vertices, so the exclusion missed them and
already-correct coordinates were mirrored. Remediated in #16.

The corroboration above was not wrong, but it was narrower than it read.
**Independent agreement is evidence about what both parties examined, and says
nothing about what neither considered.** Do not let convergence between two
implementations stand in for coverage.

**#10 — one PR carrying two separable pieces of work.**

**Disposition (owner ruling, 2026-08-08): re-scope, not close outright.** #10
bundled loss-evidence *infrastructure* with *characterization tests* of the very
defect F1 then fixed. The two halves aged in opposite directions:

- **Infrastructure — kept, re-scoped onto post-F1 `main` as #17.** Diagnostic
  loss fields, `loss()`, `LOSS_CODES`, `is_loss()`, `ImportReport`, the reserved
  fidelity vocabulary, and `test_import_diagnostics.py`. Sound, F1-independent,
  and **#11 will not build without it** — its `entities.py` calls `diag.loss(...)`
  and three codes that exist nowhere else.
- **Characterization — dropped.** `test_geometry_characterization.py` pinned
  pre-F1 behaviour as current (`circle.center.x == 5.0`, `!= expected_x`,
  `codes(...) == []`). #14 falsified every one. It was written to be inverted by
  a "PR 3" that is itself closed (#13), so rewriting it is authoring a new file,
  not rebasing one.

- #10 **closed as superseded** by #17; reasoning preserved in its closing comment.
- Branch `cs-008-import-evidence` is **retained**, not deleted, as
  `cs-008-coordinate-correctness` was for #13.
- **No commit from #10 is cherry-picked onto `main`.**
- #11 rebased onto `cs-008-loss-evidence` and retargeted to it.

*The near miss worth recording:* the first recommendation was to close #10 and
rebase #11 straight onto `main`. A trial rebase merged **textually** clean —
which is what made it look safe — and only a symbol check showed #11 calling four
things that live in #10. **A clean auto-merge is evidence about text, not about
whether the result runs.**

**A second duplicate-vocabulary collision.** #10 and #14 independently defined
`OCS_TRANSFORM_FAILED` — the same concurrent-session duplication as #13/#14, one
layer down, and undetected until #17 reconciled the two files by hand. #17 keeps
one constant and #14's comment.

*Corroboration worth keeping, and this one is sturdier:* #10 argued there must be
no `OCS_TRANSFORM_APPLIED` code, because a transform that succeeds is correct
behaviour and coding it would train readers to skim past findings that matter.
#16 reached the same principle independently when splitting `NON_PLANAR_GEOMETRY`
out of `OCS_TRANSFORM_FAILED`. Unlike the mirrored-arc agreement above, these two
examined the question from opposite directions — one deciding what *not* to emit,
the other what a successful transform must *not* be called — so the convergence is
not two parties sharing one blind spot.

## Coverage record — `docs/audits/CS-008_REAUDIT.md`

The audit declares **ten** findings, F1–F10. All ten are listed; none is omitted
because it is unremediated or undeterminable.

| Finding | Status |
|---------|--------|
| **F1** — OCS/extrusion unresolved | **Remediated.** #14, merged `c60009c`. Hardened by #16, merged `b9f181f`. |
| **F2** — fit-point spline empty geometry | **Remediated.** #11, merged `ed66bca`. Re-evaluated against the audit rather than its stacked form: 23/23 acceptance checks. |
| **F3** — rational weights discarded | as F2 |
| **F4** — knot vectors discarded | as F2 |
| **F5** — elevation dropped | **Remediated.** #19, merged `d6c7a8f`. Both 2D paths, verified against ezdxf as an independent transform oracle across units × extrusion × elevation sign. The withdrawn LWPOLYLINE/POLYLINE asymmetry is replaced by a correct paired control fixture. |
| **F6** — source handle not recoverable | **Remediated.** #19. `SourceReference` carries DXF type, handle, layer, and modelspace ordinal. |
| **F7** — `MISSING_LAYER` never emitted | **Remediated.** #19. Fires for an empty layer name or a name absent from the layer table; an omitted attribute resolves to valid layer `"0"`. |
| **F8** — docs claim loss is never silent | **Remediated.** CS-008R-CL, documentation. Still false at closure, but on *new* grounds: a mesh-flavour `POLYLINE` is silently reshaped (`has_lossy_import` stays False) and display attributes are dropped unmentioned. Claim scoped, both exceptions stated, `entities.py` docstring corrected. |
| **F9** — LWPOLYLINE vertices carry `numpy.float64` | **Accepted.** Owner ruling, 2026-08-13. Present at `entities.py:471`; every behavioural contract correct, only the debug `repr` differs. Reopening triggers recorded with the finding. |
| **F10** — periodic spline state | **Remediated.** #11 added `Spline2D.periodic`; CS-008R-CL supplied the evidence the audit lacked — two splines differing only in the PERIODIC bit, `periodic=(False, True)`, from a real DXF rather than a stub. |

**All ten findings are disposed. CS-008R is CLOSED** — see
[`docs/audits/CS-008R_CLOSURE.md`](../audits/CS-008R_CLOSURE.md), audited at
`592d461`. Seven remediated by prior PRs, one remediated at closure, one accepted,
one resolved from new evidence. Nothing deferred; nothing omitted.

The seven "remediated" rows above were **re-probed**, not read back from this
table. None was contradicted; had one been, the row would have reopened. The
importer is now under **feature freeze — defects only**.

Two limitations are carried openly rather than closed over: the mesh-`POLYLINE`
silence above is documented but unfixed — adding a diagnostic is a
runtime-vocabulary change belonging to a defect order with its own evidence — and
F9's accepted `numpy` type propagates into derived values as `numpy.bool_`, which
the JSON contract refuses at construction rather than corrupting a payload.

### Post-F1 hardening — #16

Not audit findings. Four defects found by reviewing the merged F1 change, all in
the OCS resolution machinery it introduced or touched:

| Item | Nature |
|---|---|
| Mesh POLYLINE flavours mirrored | **Regression introduced by #14.** Polygon/polyface meshes store WCS vertices but report `is_3d_polyline` false. |
| Tilted LWPOLYLINE / 2D POLYLINE resolved silently | Pre-existing silence #14 did not close; ARC and CIRCLE already reported it |
| `to_wcs` application unguarded | A mapper raising on apply escaped `translate()` and aborted the import |
| `_PLANAR_EPS` false positives | **Deliberately not changed** — loosening trades a false positive for a false negative. Boundary pinned by test. |

Also introduced there: `OCS_TRANSFORM_FAILED` no longer covers transforms that
succeeded. `NON_PLANAR_GEOMETRY` carries the successful-but-lossy case, so a
diagnostic never states a false reason.

### Import evidence completeness — #19 (F5/F6/F7)

Four rulings taken before implementation. They are recorded here because each
foreclosed a defensible alternative, and a later reader will otherwise see only
the outcome and not the choice.

| Decision | Ruling | Why the alternative was rejected |
|---|---|---|
| Absent layer attribute | Valid layer `"0"`, no diagnostic | In DXF an omitted layer group code *means* layer 0. The order's original four-way split treated "no readable value" and "layer 0" as different states; they are the same state, and flagging it would fire on ordinary valid files. |
| Provenance in equality | `compare=False` | Geometry equality stays geometric. Including it would make every imported entity unequal to every other and break future geometric comparison, while answering a question `.source` already answers directly. |
| `ordinal` basis | Modelspace position, gaps kept | A gap records that an entity did not survive. A dense index over imported entities renumbers the survivors and erases that; collection position is already available from list order. |
| `LWPOLYLINE_ELEVATION_DROPPED` | Left registered, unfired | F5 removes the condition it named. **Not repurposed** — changing an existing code's meaning makes historical findings ambiguous. Disposition belongs to the closure audit. |

The last ruling has a corollary worth keeping: **no malformed-elevation code was
added.** ezdxf rejects non-numeric elevation at assignment, so the condition
cannot be demonstrated, and naming a symbol for an undemonstrable case is exactly
how unreachable vocabulary accumulates — the problem the ruling exists to stop.

Two behaviour changes shipped deliberately and should be expected in the field:
elevated 2D polylines that previously imported at `z = 0` now import at their
true elevation, and files referencing a layer absent from the layer table now
raise an advisory `MISSING_LAYER` where they were silent. Neither withholds
geometry.

### Diagnostic `metadata` is a JSON contract — #17

A durable constraint, recorded because it binds every later increment.

`GeometryDiagnostic.metadata` is typed `Dict[str, Any]` and stays open — the
particulars worth recording differ per finding. The constraint is therefore on
**values, not schema**: `str`, `int`, finite `float`, `bool`, `None`, `list`, and
`dict` with string keys, nested freely. Anything else raises from
`__post_init__`, so no construction path bypasses it.

**Enforced rather than documented, deliberately.** Review proposed a documented
restriction plus a test, or narrower typing. Narrower typing would defeat the
field; a test catches only the cases it happens to exercise, and the hazard is
precisely that a *later* increment slips in a richer value that no existing test
sees.

The decisive argument is that three of the five failure modes are **silent**: a
`tuple` round-trips to a `list`, a non-string key returns stringified, and
`nan`/`inf` are not valid JSON — each serializes without complaint and compares
unequal on the way back, surfacing as a fixture mismatch far from the insertion.
`shared.serialization` already coerced tuple to list, so this was a live defect,
not a hypothetical one. Objects such as `Point` and `set` fail loudly instead, but
only at export, naming the serializer rather than the culprit.

Record a `Point` as `[x, y, z]` or as separate keys.

## Next orders (sequenced)

The remediation chain is complete and merged, and **closure has landed**. Steps 1
to 6 below are done. **CS-014** is the open product order (#28).

1. ~~**F8 / F9 / F10 disposition.**~~ **Done** — CS-008R-CL. F8 remediated
   (documentation), F9 accepted, F10 remediated and verified. None was dropped
   from the table.
2. ~~**CS-008R closure audit.**~~ **Done** —
   [`docs/audits/CS-008R_CLOSURE.md`](../audits/CS-008R_CLOSURE.md), audited at
   `592d461`, all ten findings disposed, seven prior remediations re-probed and
   none contradicted.
3. ~~**Freeze importer feature expansion.**~~ **In force.** The DXF importer is
   under **feature freeze — defects only**. New capabilities require a new,
   externally justified requirement; bug fixes continue through normal defect
   orders.
4. ~~**Authorize the first neutral-geometry consumer.**~~ **Done** — CS-011
   merged as #24 (`a74c99e`). The `workspace` package is the first authorized
   consumer of `GeometryCollection`: inspect, select, group, and record
   non-executable operation intent. No toolpath, feeds/speeds, or G-code.
5. ~~**Record manufacturing operation definition.**~~ **Done** — CS-012 merged
   as #26 (`29988c7`). `operations` records geometry-relative planning
   parameters on a separate `OperationPlan`. No tool, material, feeds/speeds,
   toolpath, or G-code in that increment.
6. ~~**Tool and material binding.**~~ **Done** — CS-013 merged as #27
   (`ac52fe3`). `OperationPlan.bindings` names a catalog `Tool` and
   `Material`. No feeds/speeds, machine profile, toolpath, or G-code in
   that increment.
7. **Feeds / Speeds Integration.** CS-014, open as #28. Produces an
   attributable advisory `FeedRecommendation` for a bound machining
   definition, a canonical machine profile, and an explicit requested
   `spindle_rpm`. No DOC/WOC inference, toolpath, or G-code.
8. **Toolpath Planning Foundation** — CS-015, unissued. Should begin with
   an architecture study before implementation: this is the first crossing
   from manufacturing planning into generated motion geometry. Do not jump
   from CS-014 into G-code.

**Known and unfixed, available as defect orders when someone wants them:** F9's
`numpy` type should any of its recorded reopening triggers occur. The
mesh-flavour `POLYLINE` silence documented at closure was remediated by
**CS-008R-D1** (#22, `baa566d`).

### Post-closure defect — CS-008R-D1

**Merged (#22) `baa566d`.** Not a reopening of CS-008R. Closure correctly
recorded the mesh/polyface silence as a carried limitation; this order added
the runtime evidence that closure refused to invent.

* Polygon-mesh and polyface `POLYLINE` still import as flattened `Polyline2D`.
* Each emits one unrecoverable `POLYLINE_MESH_TOPOLOGY_DROPPED` loss.
* `collection.report().has_loss` becomes true; `metadata.has_lossy_import`
  stays false while the entity is retained.
* No mesh geometry model. Coordinates unchanged from pre-fix behaviour.

### Neutral geometry consumer — CS-011

**Merged (#24) `a74c99e`.** First authorized application-layer consumer of
`GeometryCollection`. Planning state only: inspect, select, group, record
operation category. No toolpath, feeds/speeds, G-code, CAM Assist, or
Luthier domain objects.

Owner rulings recorded so they are not re-litigated:

| Decision | Ruling | Why the alternative was rejected |
|---|---|---|
| Selection / group / operation IDs | Optional `id=`; else `stable_id(kind, name, *member_ids, existing_count)` | `uuid4` / `new_id()` would make equivalent helper sequences incomparable. These IDs are **creation-context** identity, not content-addressed `GeometryRef` identity. Renaming or reconstructing a selection does not automatically preserve its ID. |
| Duplicate member IDs | Reject; preserve caller order | Silent deduplication would mutate user intent. |
| Remove a referenced selection | Reject; name dependent operation IDs | No cascade and no dangling reference. Explicit deletion order is preferable to hidden side effects. |
| Diagnostic attachment | Handle equality only: both handles present and equal | Layer/type inference invents association. Collection findings stay collection-level. Shared handles attach to each matching entity. |
| Structural validation | Raise `WorkspaceError`; `validate_workspace(workspace) -> None` | Broken IDs, dangling refs, unknown versions/kinds, and malformed documents are not advisory findings. No second findings-based authority. |
| Empty groups | Reject | A named group with no members has no useful geometry organization. |

See [`docs/GEOMETRY_WORKSPACE.md`](../GEOMETRY_WORKSPACE.md).

### Operation definition — CS-012

**Merged (#26) `29988c7`.** First authorized manufacturing-planning layer above
CS-011 `OperationIntent`. Records geometry-relative parameters (depth, contour
relation, cut-direction preference, allowances, optional peck/retract,
optional finished slot width). No tool, material, feeds/speeds, toolpath,
or G-code. Persistence is a separate `OperationPlan` document so `workspace`
does not import `operations`. CS-013 extends that same aggregate with
`bindings`. CS-014 later writes newly built plans as
`camstudio_operation_plan_v3`.

Owner rulings recorded so they are not re-litigated:

| Decision | Ruling | Why the alternative was rejected |
|---|---|---|
| Persistence ownership | `OperationPlan` in `operations`, embedding the workspace | Putting definitions on `GeometryWorkspace` would create `workspace → operations → workspace`. The dependency DAG takes priority. |
| Cardinality | At most one definition per `intent_id` | A second definition for the same intent is ambiguous for CS-013 tool/material binding. |
| Intent lifecycle | Workspace stays unaware of definitions | Cross-package wrappers would invent a reverse dependency. Callers remove the definition first; plan validation is the authority for dangling refs. |
| Slot relation | `SlotRelation.ON_PATH` even as a single-value enum | Omitting the field hides the relationship; a closed enum is the legitimate place for later members. |
| Engrave v1 | `id`, `intent_id`, `target_depth_mm` only | Repeat-pass preference drifts toward execution strategy and has no upstream contract. |
| Optional distances | Allowances/`retract_height_mm` `>= 0`; peck/slot width `> 0`; NaN/Inf rejected; peck not compared to target depth | Zero retract means the planning reference. Peck vs depth is feasibility, not structure. |
| `replace_definition` | Preserve existing ID; cannot steal another definition's intent | The one-definition-per-intent rule applies after every mutation, not only at construction. |

See [`docs/OPERATION_DEFINITION.md`](../OPERATION_DEFINITION.md).

### Tool and material binding — CS-013

**Merged (#27) `ac52fe3`.** Binds an existing CS-012 `OperationDefinition`
to one canonical catalog `Tool` and one canonical catalog `Material`.
Planning context only: which cutter and workpiece the user intends. No
suitability judgement, feeds/speeds, machine profile, toolpath, or G-code.

Owner rulings recorded so they are not re-litigated:

| Decision | Ruling | Why the alternative was rejected |
|---|---|---|
| Package ownership | Single aggregate in `operations`; `OperationPlan.bindings` | A `planning/` package would duplicate the plan document and risk an `operations ↔ planning` cycle. Dependency stays `operations → workspace`, `operations → feeds_speeds.tools/materials`. |
| Cardinality | At most one binding per definition | A second binding for the same definition is ambiguous for CS-014. Unbound machining definitions remain valid incomplete context. |
| `bind_operation` vs `replace_binding` | Second bind on a bound definition is `BindingError`; replace preserves `id` and `definition_id` | Creation versus replacement stays explicit. Replace may change only `tool_id` and `material_id`. |
| Definition removal | Reject while a binding names the definition; list dependent binding IDs; no cascade | Same referential-integrity sequence as CS-011/CS-012: `remove_binding` then `remove_definition`. |
| Error type | `BindingError(OperationDefinitionError)`; wrap catalog `ValueError` | Callers of the operation-plan API see one structural family and can still distinguish binding failures. |
| Persistence | Newly built plans are v2; load v1 retains v1 and `bindings=()`; serialize untouched v1 with no `bindings` key; first binding mutation upgrades to v2; unknown versions and catalog IDs fail closed | `read ≠ migration`. No silent `from_dict` upgrade, no placeholder resources, no dedicated upgrade helper unless a consumer later needs one. |
| Canonical objects | Reuse `Tool` / `Material`; store IDs only | Copying catalog fields onto the binding would fork identity. Resolution returns the same catalog object. |
| `REFERENCE` | Cannot be bound | The category is explicitly non-machining. |
| Summary | `BindingSummary` has no ready/score; `OperationPlanSummary` unchanged | A bound plan is not machine-ready. `definitions_without_tool_count` stays a definition count, not a readiness claim. |

See [`docs/TOOL_MATERIAL_BINDING.md`](../TOOL_MATERIAL_BINDING.md).

### Feeds / speeds integration — CS-014

**Open (#28).** Binds a CS-013 machining definition to the existing
advisory feeds/speeds calculator through a canonical `MachineProfile` and
an explicit requested `spindle_rpm`. Planning context only: attributable
advice. No DOC/WOC inference, toolpath, G-code, or machine authorization.

Owner rulings recorded so they are not re-litigated:

| Decision | Ruling | Why the alternative was rejected |
|---|---|---|
| Operating RPM | Required `spindle_rpm` on create/replace and on the wrapper | The calculator requires RPM. `MachineProfile.max_rpm` is a ceiling, not a target. Inventing 12,000/18,000 would fabricate an operating point. |
| Wrapper vs calculator RPM | Store requested `spindle_rpm` separately from `FeedRecommendation.rpm` | The calculator rounds RPM. Fingerprint/status must use the exact request. |
| Flute-less tools | `RecommendationError`; binding remains valid | `laser_diode` / `drag_knife` have `flutes is None`. Dummy flute counts would invent calculator input. This is engine inapplicability, not a bad binding. |
| Machine context | Stored on the recommendation; no plan-level selected machine | CS-013 established `binding = tool + material`. Machine belongs to recommendation context. |
| Status | `missing` / `current` / `stale`; optional contemplated `machine_profile_id` | Mismatch is stale, not mutation. Status never calls the calculator. `STALE` is structural, not unsafe. |
| Removal | Reject/no-cascade: recommendation → binding → definition | Same referential-integrity doctrine as CS-011–CS-013. `replace_binding` leaves advice in place as stale. |
| Create vs replace | Second `recommend_feeds_speeds` is `RecommendationError`; replace preserves recommendation ID and `definition_id` | Creation versus replacement stays explicit. Replace re-resolves the current binding. |
| Engagement | Never pass `doc_mm` / `woc_mm`; never map `target_depth_mm` to DOC | Final depth is not per-pass DOC. Fabricating WOC from tool diameter would invent engagement. |
| Persistence | Newly built plans are v3; load v1/v2 retains version; serialize untouched legacy without a `recommendations` key; mutation upgrades to v3 | `read ≠ migration` and `read ≠ calculation`. |
| Error type | `RecommendationError(OperationDefinitionError)`; wrap catalog/calculator `ValueError` | One structural family; advisory `FeedDiagnostic`s stay inside the payload. |

See [`docs/FEEDS_SPEEDS_INTEGRATION.md`](../FEEDS_SPEEDS_INTEGRATION.md).

### The closure standard

Stated as a gate rather than an intention, so a reviewer can hold the audit
against it instead of judging whether it feels thorough.

**CS-008R may be described as complete when, and only when, the closure audit
records one disposition for every finding F1–F10, each drawn from:**

| Disposition | Means | Requires |
|---|---|---|
| **Remediated** | the defect is fixed | the merged PR, and a probe re-run against current `main` confirming it |
| **Accepted** | real, and deliberately not fixed | the reason, and who ruled |
| **Deferred** | to be fixed later | the reason, and what would close it |
| **Not a defect** | withdrawn on evidence | the evidence that disproves it |

Three rules bind that table:

- **No finding closes by omission.** A finding absent from the table is an
  incomplete audit, not a closed finding. Silence is the one disposition that is
  never available.
- **A remediation is not self-certifying.** Seven findings are recorded as
  remediated above; the closure audit re-probes them rather than reading this
  ledger back to itself. If a re-probe contradicts a recorded remediation, the
  audit's finding wins and the row is reopened — that is the point of running it.
- **"Unable to determine" is not a disposition.** It is the reason a finding is
  still open. F10 closes as *deferred* with what would settle it, or as
  *remediated* / *not a defect* once probed — never by inheriting its own
  uncertainty.

**Unissued, and not blocking closure:** CI enforcement of this ledger's mechanical
rules (see § Enforcement status); a repository `.gitattributes` normalizing line
endings — its absence let a whole-file CRLF rewrite into #19, caught in review and
corrected, but nothing structurally prevents a recurrence.

F8, F9 and F10 are deliberately **not** combined into a single sweep. They differ
in kind — a documentation claim, a numeric-type question, and an undetermined
probe — and bundling them would let the weakest evidence carry the other two.
