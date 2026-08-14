# CS-008R — Geometry Import Remediation Closure

**Order:** CS-008R-CL · **Branch:** `cs-008r-closure` · **Parent artifact:**
[`docs/audits/CS-008_REAUDIT.md`](CS-008_REAUDIT.md)

This report answers one question:

> Does the current geometry importer satisfy the evidence, fidelity, provenance,
> and correctness contracts established by CS-008R?

**It answers yes, with two limitations carried openly** — one accepted, one
recorded as a documented silent path. The reasoning for each is below, and every
row of the finding matrix cites evidence produced against the audited commit
rather than inherited from the PR that claimed it.

---

## 1. Audit target

The CS-008R re-audit (#12) raised ten findings against `637a0ca`. Seven were
remediated across five PRs; three (F8, F9, F10) reached this closure owing a
disposition. This audit disposes all ten.

Remediation lineage, as merged:

```text
CS-008 initial importer
    ↓
CS-008R audit ................. #12   1708d4c
    ↓
F1  OCS/WCS correction ........ #14   c60009c
    ↓
post-F1 hardening ............. #16   b9f181f
    ↓
loss/evidence infrastructure .. #17   9a967f7
    ↓
F2/F3/F4 spline fidelity ...... #11   ed66bca
    ↓
F5/F6/F7 evidence completeness  #19   d6c7a8f
    ↓
governance / closure gate ..... #20   592d461
    ↓
CS-008R closure ............... THIS ORDER
```

The earlier `PR 1/3 → 2/3 → 3/3` topology is retired and is not the architecture
of record.

## 2. Commit under audit

| | |
|---|---|
| `origin/main` at audit | `592d4613387236c651eabc8363a1d3388dfcb794` |
| Closure branch at probe | `5d2468bab4bca9b972eade9c5a4b5cfdf94ec1da` |
| Worktree | `C:/tmp/cs008r-closure`, pinned from `main`, isolated from the primary checkout |

`main` was re-checked before publication. A concurrent writer was active in this
repository during the session that produced this audit; the pinned worktree is
why that could not affect the evidence.

## 3. Environment

| | |
|---|---|
| Python | 3.14.0 |
| ezdxf | 1.4.3 (optional `dxf` extra; the only third-party runtime dependency) |
| numpy | 2.4.2 — **not** a declared dependency; present transitively through ezdxf |
| pytest | 9.0.1 |
| Suite | **601 passed**, 0 failed (585 before this order) |
| Ruff | clean on all touched files |

Evidence manifest:
[`evidence/CS-008R-closure/manifest.json`](evidence/CS-008R-closure/manifest.json),
regenerable via `python tools/audits/cs008r/run_closure_probe.py`. It records no
timestamp deliberately — the audited commits identify the run, and wall-clock
metadata would make every regeneration a diff.

## 4. Finding-by-finding matrix

All ten findings appear. Per the closure standard, silence is not a disposition.

| Finding | Original status | Current evidence | Final disposition | Evidence ref |
|---|---|---|---|---|
| **F1** OCS/extrusion never resolved to WCS | confirmed defect, high | flipped extrusion → centre `(-5.0, 5.0)`; tilted extrusion resolves and raises `NON_PLANAR_GEOMETRY` without falsely claiming `OCS_TRANSFORM_FAILED` | **Remediated** (#14, hardened #16) | C1a, C1b |
| **F2** fit-point spline yields empty geometry | confirmed defect | `representation=fit`, 4 fit points retained, entity usable | **Remediated** (#11) | C2 |
| **F3** rational weights discarded | confirmed defect | `[1.0, 4.0, 4.0, 1.0]`, `rational=True`, 1:1 with control points | **Remediated** (#11) | C3 |
| **F4** knot vectors discarded | confirmed defect | 8 knots, `degree=3`, `max_knot=1.0` — not unit-scaled | **Remediated** (#11) | C4 |
| **F5** elevation dropped on both 2D polyline paths | confirmed defect | LWPOLYLINE and true 2D POLYLINE both at `z=25.0`, vertex-identical | **Remediated** (#19) | C5 |
| **F6** source handle not recoverable | confirmed defect | `entity_type=CIRCLE`, handle present, `layer='0'`, `ordinal=0`; excluded from equality | **Remediated** (#19) | C6 |
| **F7** `MISSING_LAYER` declared but never emitted | confirmed defect | omitted attribute → valid layer `'0'`, silent; empty name → `MISSING_LAYER`, geometry kept | **Remediated** (#19) | C7a, C7b |
| **F8** docs claim loss is never silent | confirmed defect, derivative | claim still false on **new** grounds: mesh POLYLINE silently reshaped (`has_lossy_import=False`); display attributes dropped unmentioned | **Remediated** (this order, documentation) | C8 |
| **F9** LWPOLYLINE vertices carry `numpy.float64` | informational | present at `entities.py:471`; every behavioural contract correct; only the debug `repr` differs | **Accepted** (owner ruling, 2026-08-13) | C9a, C9b |
| **F10** periodic spline state | unable to determine | two splines, identical control points, differing only in the PERIODIC bit: `closed=(True, True)`, `periodic=(False, True)` | **Remediated** (#11, verified here) | C10 |

**Seven remediated by prior PRs · one remediated here · one accepted · one
resolved from evidence the audit lacked. Nothing deferred. Nothing omitted.**

## 5. F1–F7 regression evidence

The closure standard states that a remediation is not self-certifying, so these
were re-probed rather than read back from the ledger. They were also asserted
*together*, against one commit — the seven remediations landed across five PRs
over five days, each green on its own branch, and green-in-isolation is a weaker
claim than green-together.

`python/tests/test_cs008r_closure.py` carries one representative invariant per
finding (16 tests). It is not a second copy of the specialised suites
(`test_geometry_ocs.py`, `test_spline_fidelity.py`, `test_geometry_elevation.py`,
`test_geometry_provenance.py`, `test_geometry_layers.py`), which remain
authoritative for detail.

No re-probe contradicted a recorded remediation. Had one, the row would have
reopened rather than closed.

## 6. F8 — documentation claims loss is never silent

**Disposition: Remediated by this order.**

The audit made F8 explicitly derivative of F1–F4/F7 — were those overturned, F8
would dissolve with them. They were remediated instead, and that *did* dissolve
the original grounds: the spline row the audit cited as self-contradicting now
reads "(none — nothing is lost)" and means it.

The claim was nevertheless still false, on grounds the audit did not have:

- a **mesh-flavour `POLYLINE`** imports as an ordinary flat chain, raises no
  diagnostic, and leaves `has_lossy_import` **False** — so a polyface reads as a
  clean import of a profile it never was. This also defeats the page's own advice
  to detect incomplete imports by reading that flag;
- **display attributes** (colour, linetype, lineweight, transparency) are dropped
  with no model field, no diagnostic, and no mention anywhere on the page.

Both verified by probe, not by reading (C8).

Corrected by scoping the claim rather than by adding diagnostics: the blanket
sentence now says most limits are signalled and names the exceptions as
exceptions; the entity-level guarantee no longer implies more than it covers; and
the same false claim in `entities.py`'s module docstring — the second location the
audit cited — is corrected in place. The attribute drop is recorded as
**deliberate**, not as a defect awaiting a fix: presentation is not geometry, and
this importer's contract is geometric fidelity.

No production behaviour changed. Adding diagnostics to make the old sentence true
would have been the opposite of this order's restraint — inventing runtime
vocabulary to rescue a documentation claim.

## 7. F9 — LWPOLYLINE vertices carry `numpy.float64`

**Disposition: Accepted — real, deliberately not fixed. Ruled by the owner,
2026-08-13.**

Confirmed present. At `entities.py:471` the identity-extrusion branch — the
*common* case — builds `Point(p[0] * scale, ...)` directly, while the OCS branch
three lines below routes through `_pt()`, which coerces. Every other entity path
coerces. So LWPOLYLINE vertices are `numpy.float64` and everything else is `float`.

Probed across the whole contract surface (C9a):

| Contract | Result |
|---|---|
| `isinstance(x, float)` | True — `numpy.float64` subclasses `float` |
| Value equality | correct |
| Arithmetic, `math.isfinite` | correct |
| `ensure_json_safe` | accepted — **by documented design**, not by accident |
| `json.dumps` | `10.0` |
| `to_dict` → `from_dict` | returns exact type `float`, equal |
| Serialized document | contains no `numpy` anywhere |
| CLI output | clean |
| **Debug `repr`** | **differs**: `Point(x=np.float64(10.0), ...)` |

The JSON metadata contract admits it deliberately: `ensure_json_safe` permits
scalar subclasses "because they compare equal to their JSON form."

### The one thing that propagates

A closure probe found the foreign type does travel further than the coordinate
(C9b), and it is recorded here rather than left for a future reader to rediscover:

- comparing a `numpy.float64` returns **`numpy.bool_`**;
- `numpy.bool_` reports its type name as `'bool'` but `isinstance(x, bool)` is
  **False** — a lookalike, not a subclass;
- `json.dumps` **refuses** it, and so does `ensure_json_safe`.

This probe crashed on its own evidence before the coercion was added, which is how
it was found.

It is nonetheless not harm *in this product*: no production diagnostic embeds a
coordinate-derived value — the metadata sites carry counts, `degree`, and strings —
so nothing is exposed. And the JSON contract **refuses** such a value at
construction rather than corrupting a payload, so the failure mode is loud.

**What would reopen F9:** a consumer requiring exact `type(x) is float`; the repr
surfacing in a user-facing artefact; or any diagnostic embedding a
coordinate-derived value. Absent those, a coercion here is cleanup without evidence
of impact, and closure is not the place for it.

## 8. F10 — periodic spline state

**Disposition: Remediated by #11, verified here.**

The audit recorded "unable to determine" — correctly refusing to convert absence
of evidence into a pass. Its P5b fixture set only the CLOSED bit, so the PERIODIC
bit was never exercised.

Two things were true at `637a0ca` and are worth separating, because only one was a
defect: the model **did** collapse DXF flags into a single boolean (witnessed), and
whether a periodic spline was distinguishable was **not** witnessed. #11 added
`Spline2D.periodic`, which addresses the first. This order supplies the evidence
for the second.

New fixture `periodic_spline.dxf`: two splines, identical control points, differing
only in the PERIODIC flag. Result (C10) — `closed=(True, True)`,
`periodic=(False, True)`, `control_points=(4, 4)`, `representation=control`. Both
closed; only one periodic; the import tells them apart.

Asserted from a real DXF on purpose. The pre-existing assertion in
`test_spline_fidelity.py` runs through a duck-typed stub, which proves the flag
decode but not that the bit survives authoring and re-reading — exactly the gap the
audit named.

Per the closure standard, "unable to determine" is not a disposition; it is the
reason a finding is still open. It is now resolved rather than deferred.

## 9. Diagnostic vocabulary disposition

Every registered code is classified, on evidence — "live" means an emission site
exists in this repository, and the site is cited in `docs/GEOMETRY_IMPORT.md`.

| Status | Count | Codes |
|---|---|---|
| **Live** | 15 | all canonical codes except the one below |
| **Reserved** | 1 | `LWPOLYLINE_ELEVATION_DROPPED` |
| **Retired** | 0 | — |

`LWPOLYLINE_ELEVATION_DROPPED` named the defect F5 fixed; the condition no longer
exists and a corpus-wide probe confirms nothing emits it (CV).

**Retirement was considered and refused.** It is public vocabulary with unknown
external consumers: a consumer matching the exact code name would break for no gain
beyond tidiness, while the cost of keeping an unreachable constant is a comment and
a table row. Compatibility outranks vocabulary hygiene. Ruled by the owner,
2026-08-13.

Nothing is retired, so "retired" remains an empty category rather than a precedent.
The code is equally deliberately **not repurposed** — a new meaning would make every
historical finding citing it ambiguous.

The classification is **enforced, not asserted**: `test_cs008r_closure.py` walks the
fixture corpus and fails if anything emits the reserved code. A reachability claim
nothing checks goes quietly false the first time someone reuses the constant, which
is the failure this reservation exists to prevent.

## 10. Remaining limitations

Carried openly. None blocks closure; all are stated where a consumer will meet them.

1. **Mesh-flavour `POLYLINE` is silently reshaped** — imports as a flat chain, no
   diagnostic, `has_lossy_import` stays False. Documented as a silent limit. Not
   fixed here: adding a diagnostic is a runtime-vocabulary change, which belongs to
   a defect order with its own evidence, not to a closure audit.
2. **Display attributes are dropped** — deliberate; presentation is not geometry.
   Now documented.
3. **`numpy.float64` on the LWPOLYLINE path** — accepted; see §7, including the
   `numpy.bool_` propagation and the triggers that would reopen it.
4. **Unreadable elevation reads as absent (`0.0`), silently** — unreachable through
   ezdxf, which rejects non-numeric elevation at assignment. No code exists for it
   because naming a symbol for an undemonstrable case is how unreachable vocabulary
   accumulates.

## 11. Constitutional boundary verification

The importer's contract is unchanged by this order.

| Concern | State |
|---|---|
| Public geometry API | unchanged |
| Schema / serialization | unchanged; round-trip verified across the corpus |
| Coordinate behaviour | verified, unchanged |
| Spline behaviour | verified, unchanged |
| Provenance | verified, unchanged |
| Diagnostics | reconciled and classified; no code added, removed, or repurposed |
| Feeds/speeds · toolpaths · G-code · machine authority | untouched |
| CAM Assist dependency | none |
| Luthier's Toolbox dependency | none |

Production code changed in exactly two places, both non-behavioural: a corrected
module docstring in `entities.py` and a classification comment in `diagnostics.py`.
No geometry consumer is authorized by this closure.

## 12. Final closure decision

> ### CS-008R geometry import remediation: **CLOSED.**

All ten findings carry an evidence-backed disposition. Seven remediations were
re-probed against the audited commit rather than accepted on the ledger's word;
none was contradicted. F8 was corrected here. F9 is accepted with its reopening
triggers recorded. F10 was resolved with evidence the audit lacked.

The DXF importer now enters:

> ### Feature freeze — defects only.

New importer capabilities require a new, externally justified requirement. Bug
fixes remain available through normal defect orders.

The mandatory next architectural question — **what is the first authorized consumer
of trustworthy neutral geometry?** — belongs to a new dev order and is deliberately
not answered here.
