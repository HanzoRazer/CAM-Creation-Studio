# CS-008R — DXF Geometry Import Conformance Re-Audit

> ## Audited implementation: `637a0cafe3eed01792f90eff4ad093e41a519c24`
>
> Every finding below describes **that commit and no other.** This report does not
> become an assessment of later code merely because it is committed on a newer
> `main`, and it does not evaluate any parallel or subsequent implementation.

**Status:** ratified — Phase 8 independent review complete with corrections applied
**Author adversarial review:** completed
**Independent review:** completed; findings ratified subject to the editorial
corrections recorded in §13
**Authorized activity:** read-only verification and evidence capture
**Remediation authorized:** none — remediation is deferred to separately
authorized, focused dev orders (§8)

### Verdict

> CS-008 is **substantially architecturally conformant**, but its
> **import-evidence contract is not fully conformant.** Focused remediation is
> warranted.

---

## 1. Provenance

| Witness | Value |
|---|---|
| Repository | `CAM-Creation-Studio` |
| Remote | `https://github.com/HanzoRazer/CAM-Creation-Studio.git` |
| Audited commit (pinned) | `637a0cafe3eed01792f90eff4ad093e41a519c24` |
| Audit worktree | `C:\tmp\cs008_audit` |
| HEAD state | detached |
| Worktree status at start and end | clean, 0 untracked |
| Git common dir | `C:/Users/thepr/Downloads/CAM-Creation-Studio/.git` |
| Python executable | `C:\Python314\python.exe` |
| Python version | 3.14.0 |
| Package `__file__` | `C:\tmp\cs008_audit\python\cam_creation_studio\__init__.py` |
| ezdxf version | 1.4.3 |
| NumPy | 2.4.2 — **not** a declared dependency; repo never imports it; arrives transitively via ezdxf |

The harness asserts `cam_creation_studio.__file__` resolves under `C:\tmp\cs008_audit`
before producing any evidence, and aborts otherwise.

### 1.1 Declared deviation — session root

CS-008R §4 directs that the audit run from a session rooted in `CAM-Creation-Studio`
or the audit worktree. The executing session's primary working directory is
`CAM-Assist-Blueprint` and cannot be re-rooted in place. Mitigations applied:

- every audit action confined to `C:\tmp\cs008_audit` (an authorized working
  directory) and `C:\tmp\cs008_evidence`;
- all evidence artifacts relocated out of the CAM-Assist-keyed scratch path;
- no CAM Assist repository file read, written, staged, or committed during CS-008R;
- the parked `cam-a23-creation-studio-capability-profile` branch untouched.

The reviewer should weigh this deviation explicitly rather than treat it as resolved.

### 1.2 Concurrent activity observed during the audit

The live checkout moved twice while CS-008R was running. Neither event touched the
pinned worktree — which is the isolation requirement doing its job — but both are
recorded because they bear on Phase 10 sequencing.

| Time | Event |
|---|---|
| 2026-08-05 23:57 | `cs-009-export-preflight` created and committed (`3fb0075`), later merged as PR #9 → `main` = `637a0ca` |
| 2026-08-06 14:22 | branch `cs-008-import-evidence` created from `637a0ca`; working tree left **dirty** |

At the time of writing, `cs-008-import-evidence` is 0 commits ahead of `main` and
carries uncommitted modifications to **`python/cam_creation_studio/geometry/diagnostics.py`**
and **`python/cam_creation_studio/geometry/models.py`** — two of the files under audit.

CS-008R §3 places remediation out of scope and §13 lists altering diagnostics and
`has_lossy_import` among the non-goals until findings are ratified. If that work is
remediation, it began before this report was reviewed and would pre-empt Phase 10;
if it lands, these findings describe a commit that no longer reflects the working
state. This is reported as an observation, not an accusation — authorship and intent
were not investigated.

---

## 2. Baseline reproduction (Phase 1)

Both prior counts were treated as claims and independently re-derived inside the
pinned worktree.

| Command (from `C:\tmp\cs008_audit\python`) | Result | Exit |
|---|---|---|
| `python -m pytest tests/test_geometry_import.py tests/test_geometry_models.py tests/test_geometry.py -q` | **65 passed** in 4.09s | 0 |
| `python -m pytest -q` | **384 passed** in 8.73s | 0 |

Both prior reference observations are **reproduced**.

Note on the 384: an earlier measurement of 384 was taken while CS-009 was
uncommitted in the live tree and was therefore unverifiable at the time. Re-derived
at the pinned post-merge commit it is identical, so the figure stands — but only
the pinned measurement should be cited.

Green tests are treated as regression status only. Every loss path below has a
direct probe; none relies on test success as evidence of fidelity.

---

## 3. Architectural conformance (Phase 2)

Verified against `637a0ca` by inspection of the live paths.

| Requirement | Evidence | Result |
|---|---|---|
| `ezdxf` optional | `dependencies = []`; `dxf = ["ezdxf>=1.4,<2"]` | PASS |
| Guarded import | single `import ezdxf` inside `_require_ezdxf()` (`importer.py:46`), lazy; no module-load import anywhere else | PASS |
| Actionable absence error | `EzdxfNotInstalled` carrying `pip install cam-creation-studio[dxf]` | PASS |
| No runtime dep expansion | required deps still empty | PASS |
| Source entity order preserved | P1: `['line','arc','circle','polyline','polyline','spline']` | PASS |
| Deterministic deserialization | P16: two imports serialize identically | PASS |
| Shared `Point` reused | `geometry/{entities,models,bounds,summary}.py` import from `shared.geometry` | PASS |
| Shared `Bounds` reused | same | PASS |
| No parallel `Point2D` | repository search: none | PASS |
| No parallel bounds authority | only `shared/geometry.py:31` | PASS |
| Modules by responsibility | `bounds, diagnostics, entities, importer, layers, models, summary` (1.0–8.4 KB) | PASS |
| No machining intent inference | no toolpath/feed/speed logic; three prose matches only | PASS |
| No CAM Assist dependency | repository search: zero matches | PASS |

**Informational:** `preview/toolpath_model.py:53` defines a second `Point`. It was
introduced by `773f4c0` ("Pivot core to Python"), predates CS-008, and lies outside
the audited surface. Noted so the "no parallel primitive" claim is not overstated
repository-wide.

**Audited paths (exact):**

```text
python/cam_creation_studio/geometry/{__init__,bounds,diagnostics,entities,importer,layers,models,summary}.py
python/cam_creation_studio/shared/{geometry,units,serialization,numbers}.py
python/tests/{test_geometry.py,test_geometry_import.py,test_geometry_models.py}
docs/GEOMETRY_IMPORT.md
python/pyproject.toml
```

---

## 4. Probe results

26 probes. Raw evidence in `probe_manifest.json`.

| Classification | Count |
|---|---|
| FULLY_PRESERVED | 9 |
| APPROXIMATED_WITH_DIAG | 4 |
| SKIPPED_WITH_DIAG | 2 |
| SILENTLY_LOST (harness auto-label) | 11 |

**The harness's auto-labels are mechanical and three are corrected below by author
review.** Corrected totals: **8 SILENTLY_LOST**, 11 FULLY_PRESERVED, 1 unable to determine.

---

## 5. Findings

Each finding carries an independent *class*, *severity*, and *disposition*.
Severity is re-derived from evidence, not from defect class and not inherited.

---

### F1 — OCS/extrusion never resolved to WCS

- **Class:** `coordinate_correctness` · **Severity:** high · **Disposition:** confirmed defect
- **Probes:** P7a, P7b, P7c (P7d control; P14b consequence) · **Commit:** `637a0ca`
- **Expected (oracle `ezdxf.math.OCS(extrusion).to_wcs`):** circle authored at OCS
  `(10, 4)` with extrusion `(0,0,-1)` resolves to WCS `(-10.0000, 4.0000)`
- **Actual:** `(10.0000, 4.0000)`
- **Diagnostics:** none · **`has_lossy_import`:** `False`
- **Control:** P7d, default extrusion `(0,0,1)`, imports correctly — isolating
  extrusion handling from general coordinate handling
- **Affected:** `geometry/entities.py::translate` (`_pt`, and the LINE/ARC/CIRCLE/
  LWPOLYLINE/POLYLINE/SPLINE branches); no OCS handling exists anywhere in the package
- **Why high, not critical:** geometry is materially misplaced and nothing signals
  it, so a consumer may reasonably treat it as valid. It is not critical because
  CS-008 output is authoring/education-facing with human review downstream and no
  demonstrated direct path to machine execution. Severity should be revisited if a
  consumer ever drives an execution-adjacent stage from imported geometry.
- **Scope note:** mirrored/rotated entities are ordinary CAD output, so this is not
  an exotic input. ARC additionally mirrors sweep direction under a flipped
  extrusion; the model stores raw `start_angle`/`end_angle` unchanged.
- **Recommended disposition:** focused order, `coordinate_correctness` family

---

### F2 — Fit-point spline yields empty geometry while the collection-level lossy signal stays clear

- **Class:** `evidence_diagnostic` · **Severity:** high · **Disposition:** confirmed defect
- **Probe:** P2 · **Commit:** `637a0ca`
- **Expected:** shape evidence for the 3 fit points, or a loss signal reaching
  `has_lossy_import`
- **Actual:** `Spline2D(control_points=0, bounds=None)`; `raw=1 kept=1 unsupported=0`
- **Diagnostics:** `INVALID_SPLINE` **is** raised · **`has_lossy_import`:** `False`
- **Affected:** `geometry/importer.py` (loss accounting), `geometry/models.py::ImportMetadata.has_lossy_import`
- **Correction to the prior audit:** the earlier report implied this loss was
  silent. It is not — `INVALID_SPLINE` fires at entity level. The defect is
  narrower and lives at the collection level: `has_lossy_import` is documented in
  `docs/GEOMETRY_IMPORT.md` as the way "to detect an incomplete import at a
  glance", and it reports clean for an entity that carries no geometry. Severity
  remains high because that is precisely the case where silent loss makes an
  incomplete import look complete.
- **Recommended disposition:** focused order, spline fidelity / loss-evidence family

---

### F3 — Rational spline weights discarded without runtime evidence

- **Class:** `evidence_diagnostic` + `representation_fidelity` · **Severity:** medium · **Disposition:** **confirmed defect** (documented limitation is mitigating context only)
- **Probe:** P4, plus a dedicated `has_lossy_import` witness · **Commit:** `637a0ca`
- **Expected:** weights `[1.0, 8.0, 8.0, 1.0]` retained, or loss visible in the
  runtime evidence surface
- **Actual:** source carried 4 weights; weighted and unweighted splines import
  indistinguishably
- **Runtime evidence surface:** `diagnostics = (none)` ·
  **`has_lossy_import` = `False`** · `raw/kept/unsupported = 1/1/0`
- **Documentation:** `docs/GEOMETRY_IMPORT.md` fidelity table — "SPLINE knot
  vectors, weights, fit points | Dropped; only control points + degree kept |
  (documented; hull-bounded)". The Signal column honestly declares no diagnostic.
- **Affected:** `geometry/models.py::Spline2D` (no weight field); `geometry/diagnostics.py` (no weight-loss code)
- **Why this is a defect and not merely a documented limitation:** documentation
  status and runtime-evidence adequacy are **separate questions**. The first is
  satisfied; the second is not. The artifact presents a complete import — no
  diagnostic, `has_lossy_import` clear — for a curve whose shape has materially
  changed. A global prose disclosure does not cure a per-entity runtime
  contradiction, because a consumer inspecting the artifact sees nothing wrong.
  The author's original classification conflated the two questions; this is the
  corrected ruling.
- **Why medium, not high:** the control-point hull still bounds the curve and the
  omission is disclosed, so a diligent consumer has a path to the limitation.

---

### F4 — Knot vectors discarded without runtime evidence

- **Class:** `evidence_diagnostic` + `representation_fidelity` · **Severity:** medium · **Disposition:** **confirmed defect** (documented limitation is mitigating context only)
- **Probe:** P5a, plus a dedicated `has_lossy_import` witness · **Commit:** `637a0ca`
- **Expected:** 8 source knot values retained, or loss visible in the runtime
  evidence surface
- **Actual:** model fields are `control_points, degree, closed, layer, kind`; no
  knot field. Source knots `[0,0,0,0,1,1,1,1]`
- **Runtime evidence surface:** `diagnostics = (none)` ·
  **`has_lossy_import` = `False`** · `raw/kept/unsupported = 1/1/0`
- **Documentation:** same fidelity-table row as F3
- **Ruling:** identical to F3 — documented, but invisible at runtime. Confirmed
  evidence defect with the documentation recorded as mitigating context.

---

### F5 — Elevation attribute dropped on both 2D polyline paths

- **Class:** `representation_fidelity` · **Severity:** low · **Disposition:** undocumented limitation
- **Probes:** P8a (LWPOLYLINE), P8c (POLYLINE-2D control), P8b (POLYLINE-3D reference)
- **Expected:** vertex `z = 12.0` where the elevation attribute is set
- **Actual:** LWPOLYLINE `z = [0.0]`; POLYLINE-2D `z = [0.0]`; POLYLINE-3D `z = [12.0]`
- **Diagnostics:** none · **`has_lossy_import`:** `False`
- **Correction to the prior audit:** the earlier report called this an asymmetry
  between the LWPOLYLINE and POLYLINE paths. **P8c disproves that.** A 2D polyline
  drops the elevation attribute exactly as LWPOLYLINE does; the apparent asymmetry
  was an artifact of comparing against a 3D polyline, which carries z in its
  vertices rather than in an attribute. This is a *uniform 2D-scope limitation*,
  not an inconsistency, and the severity drops accordingly.
- **Residual defect:** the fidelity table's row "3D solids / meshes / Z-depth
  beyond point Z | Not represented | `UNSUPPORTED_ENTITY`" names a signal that does
  **not** fire for an elevated polyline. Behaviour is defensible under a 2D charter;
  the documented signal is wrong.

---

### F6 — Source handle not recoverable from imported entities

- **Class:** `metadata_consistency` · **Severity:** low · **Disposition:** undocumented limitation
- **Probe:** P10b · **Commit:** `637a0ca`
- **Expected:** source handles `['8A','8B']` traceable from imported entities
- **Actual:** no `handle` attribute on any entity model
- **Diagnostics:** none
- **Affected:** `geometry/models.py` (entity dataclasses); handles are read in
  `importer.py` for `DUPLICATE_HANDLE` detection and diagnostic location only
- **Note:** layer is fully preserved (P10a). Nothing in the docs promises handle
  preservation, but nothing discloses its absence either, and CS-008 frames itself
  as preserving source evidence — hence "undocumented limitation" rather than defect.
- **Open question for the contract owner:** this remains an undocumented
  limitation **unless the original CS-008 contract explicitly required persistent
  handles**, in which case it becomes a confirmed defect. This audit did not have
  the original CS-008 handoff text and therefore could not settle that question;
  it is flagged rather than assumed either way.

---

### F7 — `MISSING_LAYER` is declared but never emitted, and the state *is* reachable

- **Class:** `evidence_diagnostic` · **Severity:** low · **Disposition:** confirmed defect
- **Probe:** P11 · **Commit:** `637a0ca`
- **Reachability first (per CS-008R instruction):** an entity referencing
  `GHOST_NOT_IN_TABLE` survives save→reload with the layer **absent from the layer
  table** (`present in reloaded layer table = False`). ezdxf does not normalize or
  reject the state, so the case is genuinely constructible — this is not a finding
  forced by the existence of a constant.
- **Expected:** `MISSING_LAYER` raised, or the state proven unconstructible
- **Actual:** state constructible; `MISSING_LAYER` never emitted; layer name
  preserved verbatim
- **Corrected classification:** the harness auto-labelled this `SILENTLY_LOST`.
  **That is wrong** — the layer name is fully preserved, so no information is lost.
  The defect is a declared diagnostic that is unreachable in practice.
- **Affected:** `geometry/entities.py::_layer_of` (defaults to `"0"` without
  consulting the layer table); `geometry/diagnostics.py` exports `MISSING_LAYER` in
  `CANONICAL_CODES`

---

### F8 — Documentation claims loss is never silent

- **Class:** `documentation_consistency` · **Severity:** low · **Disposition:** confirmed defect, **derivative**
- **Dependency (explicit):** F8 is **not an independently discovered geometry
  defect.** It exists **only because** F1, F2, F3, F4 and F7 confirm runtime
  evidence defects at `637a0ca`. The documentation claim is false precisely and
  solely to the extent those findings stand. Were they all overturned, F8 would
  dissolve with them; its wording should be revised to match whichever of them
  survive remediation.
- **Evidence:** `docs/GEOMETRY_IMPORT.md:50-52` — "These are surfaced as diagnostics
  (or an unsupported-entity drop), never silent"; `geometry/entities.py:13` —
  "Fidelity limits (surfaced as diagnostics, never silent)"
- **Contradicted by:** its own table row for splines (Signal = "(documented;
  hull-bounded)", i.e. no diagnostic), and empirically by F3, F4 (no diagnostic,
  `has_lossy_import` clear), F7 (declared diagnostic never emitted), and F1/F2
- **Note:** the fidelity table itself is honest; the blanket lead-in sentence is not

---

### F9 — LWPOLYLINE vertices carry `numpy.float64`

- **Class:** `serialization_compatibility` · **Severity:** informational · **Disposition:** undocumented limitation
- **Probe:** P15 · **Commit:** `637a0ca`
- **Expected:** every coordinate a plain Python `float`
- **Actual:** `LWPOLYLINE.vertex.x → float64`; `POLYLINE.vertex.x → float`; `LINE.start.x → float`
- **Serialization:** `json.dumps` succeeds; reparsed values are ordinary `float`
- **Corrected classification:** the harness auto-labelled this `SILENTLY_LOST`.
  **That is wrong** — no information is lost and serialized output is valid JSON.
- **Cause:** `entities.py` LWPOLYLINE branch builds `Point(p[0] * scale, ...)`
  without the `float()` coercion `_pt()` applies on every other path
- **Fragility:** the dataclass is annotated `float` but holds `numpy.float64`; JSON
  output survives only because `numpy.float64` subclasses `float`
- **NumPy status:** not a declared project dependency, never imported by the repo;
  present transitively through ezdxf. No dependency was added for this audit.

---

### F10 — Periodic spline state: unable to determine

- **Class:** `representation_fidelity` · **Severity:** informational · **Disposition:** unable to determine
- **Probe:** P5b · **Commit:** `637a0ca`
- **What was witnessed:** a spline with the CLOSED flag (`flags=1`) imports with
  `closed=True`; the model collapses DXF flags into a single boolean
- **What was not witnessed:** the fixture never set the PERIODIC bit (2), so
  whether a genuinely periodic spline is distinguishable from a merely closed one
  was **not** tested. The harness auto-labelled this `FULLY_PRESERVED` on the
  strength of the closed case alone; that label overstates the evidence.
- **Recommended:** a follow-up probe constructing a periodic spline before any
  conclusion is drawn

---

## 6. Disproven / conformant

| Area | Probe | Result |
|---|---|---|
| Source entity order across mixed kinds | P1 | conformant |
| Control-point spline order, degree, closed | P3 | conformant |
| Invalid spline diagnosis | P6 | `INVALID_SPLINE`, geometry retained |
| Bulge, LWPOLYLINE **and** POLYLINE | P9a, P9b | `POLYLINE_BULGE_IGNORED` on both |
| Layer preservation | P10a | verbatim |
| Unsupported entities (TEXT, ELLIPSE) | P12a | 2× `UNSUPPORTED_ENTITY`, `has_lossy_import=True` |
| Malformed entities | P12b | all three codes; no crash; geometry retained |
| Unit normalization, 8 mapped codes | P13 | exact to 1e-12 |
| Unmapped INSUNITS (11, 12, 15, 16) | P13 | explicit 1.0 fallback + `UNKNOWN_UNITS` |
| Bounds from post-scale coordinates | P14a | exact, incl. +Y cardinal crossing |
| Determinism + source immutability | P16 | identical serialization; source hash unchanged |

The `has_lossy_import` mechanism works correctly for its documented case —
entities *dropped* as unsupported (P12a). F2 is the case it does not cover:
an entity *retained* but empty.

---

## 7. Author adversarial review

Completed before handoff. Challenges applied and their outcomes:

1. **Inherited assumptions.** All prior-audit verdicts discarded and re-derived.
   Two prior claims were corrected against me: the fit-point spline is *not*
   silent (F2), and the elevation behaviour is *not* asymmetric (F5).
2. **Unsupported expected behaviour.** P8b was a weak control — a 3D polyline
   trivially carries z. P8c was added as a like-for-like control and *reversed*
   the finding. The weak probe was fixed rather than the conclusion.
3. **Severity inflation.** F1 held at high, not critical: no demonstrated path to
   unsafe downstream behaviour without a human detection point. F5 dropped from
   the prior audit's framing to low once P8c disproved the asymmetry.
4. **2D scope vs incorrect transformation.** Explicitly separated. F5 is a scope
   limitation; F1 is a transformation defect. These are not the same class and are
   routed to different remediation families.
5. **Claims from source inspection only.** Every finding has an executable probe.
   Architectural conformance (§3) is inspection-based and is labelled as such.
6. **Oracle independence.** `ezdxf.math.OCS` is not used anywhere in the importer,
   so it does not share the code under test. Caveat: it is the same *library* that
   parsed the file, so a systematic ezdxf-wide OCS misunderstanding would not be
   caught. An independent hand-computed reflection for the `(0,0,-1)` case agrees
   (x → −x), so F1 does not rest on ezdxf alone.
7. **Diagnostics vs `has_lossy_import` vs geometry.** Reconciled per finding. F2
   exists precisely because those three disagree.
8. **Harness auto-labels.** Mechanical and not authoritative. Three were corrected
   by review: F7 and F9 were mislabelled `SILENTLY_LOST` when nothing is lost, and
   F10 was mislabelled `FULLY_PRESERVED` on untested evidence.

Known coverage gaps, declared rather than papered over: periodic splines (F10);
INSERT/block expansion not probed beyond the unsupported-entity path; no probe for
very large coordinate magnitudes or float precision limits.

---

## 8. Recommended disposition

No remediation is authorized by this order. If the findings are ratified, the
natural split — keeping coordinate placement separate from representational
evidence, per CS-008R §4.9 — is:

**Family A — coordinate correctness**
- F1 OCS/extrusion resolution (high)
- F5 elevation-attribute behaviour and its documented signal (low)

**Family B — spline fidelity and loss evidence**
- F2 `has_lossy_import` accounting for retained-but-empty entities (high)
- F3 weight-loss diagnostic (medium)
- F4 knot-loss diagnostic (medium)
- F10 periodic-state probe, before any change (informational)

**Family C — metadata, diagnostics, documentation**
- F6 handle traceability (low)
- F7 `MISSING_LAYER` reachability (low)
- F8 documentation "never silent" claim (low)
- F9 `float()` coercion on the LWPOLYLINE path (informational)

F1 and F2 are the only findings that plausibly justify near-term work.

---

## 9. Evidence manifest

| Artifact | SHA-256 | Bytes | Published |
|---|---|---|---|
| `CS-008_probe.py` | `9e0b4ae6d5d9ca54e5d0fbf09cf091a4826b2d19cf174e54d959f414b4f267df` | 23792 | no — retained externally |
| `probe_manifest.json` | `e6b29db4c766439ce279124dc378024c09c31b7fcd925bb54a215a95171459f0` | 10440 | yes |

Both hashes are **post-P8c**: the harness was amended during author review to add
the like-for-like polyline control, re-run, and only then hashed. The manifest
recorded by that run contains 26 probe results, which confirms P8c is included.

**This report deliberately does not state its own SHA-256.** A document cannot
claim a hash of bytes that do not yet exist, and hand-editing `probe_manifest.json`
to carry it would destroy that file's provenance as pure harness output —
re-running the harness would no longer reproduce it. The final report hash belongs
in the publication commit or PR description, computed after the bytes are final.

### Reproduction

```text
harness            CS-008_probe.py
working directory  C:\tmp\cs008_evidence
invocation         python CS-008_probe.py
audited commit     637a0cafe3eed01792f90eff4ad093e41a519c24
required worktree  C:\tmp\cs008_audit  (detached, clean)
python             C:\Python314\python.exe  3.14.0
ezdxf              1.4.3
temporary files    DXF fixtures written to a fresh system temp dir per run;
                   probe_manifest.json written beside the harness;
                   nothing written inside either repository
```

The harness aborts unless the imported package resolves under the pinned worktree.

### Exit-code semantics — read this before citing exit 0

```text
Exit 0 means the characterization harness completed without infrastructure failure.
It does not mean that the geometry behaviors passed conformance.
Probe classifications constitute the audit results.
```

The harness computes and records a classification for every probe but **asserts
none of them**. A run in which every probe returned `SILENTLY_LOST` would still
exit 0. This is deliberate for a characterization tool — it records rather than
gates — but it makes the exit code useless as a pass signal.

### Known harness weaknesses (recorded, not material to the verdict)

- **P4 comparison method.** `Spline2D` exposes no `to_dict`, so the
  weighted-vs-unweighted equivalence check falls back to comparing dataclass
  `repr()` strings. For the current frozen dataclass of floats this is adequate
  **corroborating** evidence, but it is **not canonical structural equality** and
  the report does not claim it as such. The F3 ruling additionally rests on the
  direct `has_lossy_import` / diagnostics witness, which does not depend on it.
- **P14b aliasing.** The argument expression `d14b if (d14b := d7a) else []`
  evaluates to `d7a` unconditionally; the walrus is pointless. Harness cleanup
  only — no bearing on the audit verdict.
- **Dead computation.** `all_float_subclass` is computed and never used. It forms
  no part of the P15 evidence or the F9 ruling.

Should the characterization ever be needed as a regression guard, these cases
should be rewritten as focused asserting tests rather than the scratch harness
being promoted wholesale.

---

## 10. Clean-worktree proof

```text
path      C:\tmp\cs008_audit
HEAD      637a0cafe3eed01792f90eff4ad093e41a519c24
detached  YES
status    clean (no output from git status --porcelain)
untracked 0 files
```

No production file or existing test was modified. No branch was created. Nothing
was staged, committed, pushed, tagged, or released.

---

## 11. Placement (ruled)

`docs/audits/` did **not** exist at `637a0ca`; `docs/` contained only
`architecture/` and `migration/`. The reviewer ruled that this is a conformance
audit rather than a migration artifact, so filing it under `docs/migration/`
merely because an older audit lives there would misclassify its purpose.

Published:

```text
docs/audits/CS-008_REAUDIT.md
docs/audits/evidence/CS-008/probe_manifest.json
```

`CS-008_probe.py` is **not** published. Its role was characterization, and its
deliberate non-gating exit semantics make it unsuitable to masquerade as a test or
CI utility without modification. It is retained externally with its SHA-256 and
reproduction instructions (§9).

---

## 12. Parallel implementation notice

```text
Audit baseline: 637a0ca
Parallel branch observed: cs-008-import-evidence
Audit verdict unaffected by parallel branch
Parallel changes not reviewed or ratified by CS-008R
```

Work on that branch was neither inspected nor merged into any finding here. It
must not become the de facto specification: any implementation on it is to be
evaluated against the approved focused remediation orders, not accepted merely
because it exists.

---

## 13. Phase 8 disposition and applied corrections

Independent review: **passed with required editorial corrections.** No further
technical investigation was required before publication. The corrections below
were applied to this document before it was committed.

| # | Correction | Applied |
|---|---|---|
| 1 | F3/F4 reclassified as confirmed evidence defects; documentation recorded as mitigating context only | §5 F3, F4 |
| 2 | Stale report self-hash removed; final hash deferred to the publication commit / PR description | §9 |
| 3 | Exit-code semantics stated explicitly (exit 0 ≠ conformance) | §9 |
| 4 | P4 `repr()` comparison recorded as corroborating, not canonical structural equality | §9 |
| 5 | Unused `all_float_subclass` recorded as dead computation, excluded from evidence | §9 |
| 6 | P14b aliasing expression recorded as harness cleanup | §9 |
| 7 | F10 left unresolved — absence of evidence is not converted into a pass | §5 F10 |
| 8 | F8 made explicitly derivative of F1–F4/F7 rather than an independent geometry finding | §5 F8 |

Additional: F6 carries an explicit open question for the contract owner, since
this audit lacked the original CS-008 handoff text and could not establish whether
persistent handles were contractually required.

**Ratified finding severities:** F1 high · F2 high · F3 medium · F4 medium ·
F5 low · F6 low · F7 low · F8 low · F9 informational · F10 unable to determine.

---

## 14. Status

```text
Phase 7 evidence collection:  COMPLETE
Author adversarial review:    COMPLETE
Phase 8 independent review:   COMPLETE WITH CORRECTIONS
Findings ratified:            YES
Production remediation:       NOT YET AUTHORIZED
CS-010:                       STILL QUEUED
```

Remediation sequencing (§8): **F1 alone** as the first coordinate-correctness
order; **F2/F3/F4** as a second, coherent spline fidelity/evidence order;
**F7/F8** as a smaller diagnostic and documentation-consistency order. F1's
correctness change must not be mixed with the evidence changes.

This publication adds audit documentation only. No production file, existing test,
or dependency was modified at any point in CS-008R.
