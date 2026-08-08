# Session Integrity Notice — 2026-08-07

**Status:** permanent governance artifact · **Order:** CS-REC-01
**Repository:** CAM-Creation-Studio (`HanzoRazer/CAM-Creation-Studio`)
**Affected session root:** a local checkout of this repository. The specific
filesystem path is deliberately not recorded — it is environment-specific and
carries no governance meaning; what matters is *which repository* the session was
rooted at, not where the clone lived.

Cross-repository context contamination occurred during an extended working
session. This notice records what was contaminated, what was not, and how to
tell the difference. It is an audit trail, not an apology.

> **Reading note.** Sections 1–2 and 5–6 are durable: cause, evidence policy, and
> operating rules. Sections 3–4 describe repository state **as it stood on
> 2026-08-07** and are a historical record, not a live status board. Where they
> name a PR, GitHub is authoritative — see
> [`dev_orders/LEDGER.md`](dev_orders/LEDGER.md) § Source of truth.

---

## 1. What happened

An implementing session rooted in **CAM-Creation-Studio** repeatedly received
planning artifacts — dev orders, review verdicts, and recovery plans — written
for **CAM-Assist-Blueprint**, a separate product with its own constitution.
Contamination ran in both directions: Blueprint verdicts arrived here, and this
session's work was summarized back into Blueprint planning.

Four separate messages referenced work absent from this thread: CAM-A17–A23
capability profiles, traceability bundles, Production Shop handoff, and a
CS-008 audit the session could not see. One attributed positions to the
implementing session that it had never taken.

### Root cause

Two contributing mechanisms, in order of severity:

1. **Concurrent sessions in one repository.** At least one other agent session
   was operating in CAM-Creation-Studio at the same time. Neither session could
   see the other's branches, PRs, or in-flight work. This is not conversational
   bleed; it produced duplicate implementations (§4).
2. **Recycled identifiers.** `CAM-CS-02` named two unrelated orders — an
   export-preflight spec later reissued as CS-009, and a shared fret-math study.
   A reused identifier makes cross-thread misrouting hard to detect.

---

## 2. Evidence hierarchy

The distinction that makes recovery tractable:

| Tier | Kind | Status |
|------|------|--------|
| 1 | Commits, tests, and probes executed against this repository | **Authoritative.** Unaffected. |
| 2 | Repository documentation and merged audits | **Authoritative.** |
| 3 | Planning derived from another repository's state | **Not authoritative.** Re-derive. |
| 4 | Claims about artifacts the session never saw | **Void.** |

Applying the failed-CI rule — *keep verified commits, discard derived planning,
regenerate from the repository* — most engineering work in this repository
survives, because it was grounded in probes rather than in conversation.

---

## 3. Unaffected work

Every commit below was verified against this repository at the time it was made:
tests executed, defects reproduced with probes, `ezdxf` used as the external
reference for coordinate maths. None derives from Blueprint planning.

| Commit / PR | Work | Evidence |
|---|---|---|
| `831680f` (#8) | CAM-CS-01 authority grounding | Repository inventory; 310 tests |
| `db68f16` | Product boundary ratified | — |
| `637a0ca` (#9) | CS-009 export preflight | 384 tests |
| `1708d4c` (#12) | CS-008R conformance re-audit | Independent probes |
| #10, #11, #13 | CS-008 fidelity remediation | 493 tests; defects reproduced |

*State as of 2026-08-07.* #13 has since been closed as superseded (§4.2); #10 and
#11 remain open. The evidence column is what mattered for recovery — each row was
grounded in executed tests, and that does not change when a PR's status does.

---

## 4. Contaminated planning — and one duplicate implementation

### 4.1 The audit was in this repository the whole time

The implementing session stated repeatedly that the referenced CS-008 audit
"has never appeared in this session" and treated its findings as unavailable.
**That was wrong.** `docs/audits/CS-008_REAUDIT.md` was merged to `main` as
PR #12 / `1708d4c` on 2026-08-07T05:17:41Z, pinned to commit `637a0ca` — the
exact commit the remediation branched from.

The failure was procedural: the session searched other repositories and the
conversation for the audit, and never re-checked `main` or the PR list of the
repository it was working in. **Corrective rule:** before declaring an
artifact missing, enumerate the working repository's branches, PRs, and `main`.

### 4.2 Duplicate remediation of the same defect

PR **#13** (`cs-008-coordinate-correctness`) and PR **#14**
(`cs-008-f1-coordinate-correctness`, opened 2026-08-07T07:52:41Z by a
concurrent session) both fix audit finding **F1 — OCS/extrusion never resolved
to WCS**, and both modify `geometry/entities.py` and `geometry/diagnostics.py`.

Neither session knew of the other. This is the contamination's most concrete
cost.

**Resolved 2026-08-07 by owner ruling: #14 is canonical.** It branches from
`main`, implements F1 in isolation, and leaves F2–F7 untouched. #13 was closed as
superseded — it was stacked behind #10/#11 and mixed F5 into F1 — with its
implementation notes preserved in its closing comment and its branch retained.
No commit from #13 is cherry-picked onto `main`. See
[`dev_orders/LEDGER.md`](dev_orders/LEDGER.md) for the full disposition.

Both implementations independently derived the same mirrored-arc angle rule and
both correctly left `LINE` untransformed, which is meaningful corroboration —
but it cost two sessions' work to obtain, which is the point of rule 4 in §6.

**Sequel, recorded 2026-08-08.** #14 merged as `c60009c`. Review of the merged
change then found a regression it had introduced: POLYLINE *mesh* flavours store
WCS vertices but report `is_3d_polyline` false, so F1's exclusion missed them and
mirrored coordinates that were already correct. Remediated in #16.

This qualifies the corroboration above, and the qualification is the durable
lesson: **independent agreement confirms the part both implementations reasoned
about, and is silent on the part neither considered.** Two sessions agreeing on
the arc rule said nothing about the entity flavour both overlooked. Convergence is
evidence about what was examined, never coverage of what was not.

### 4.3 Remediation coverage was narrower than claimed

The audit declares **ten** findings, F1–F10. Measured against them, the
remediation in #10/#11/#13 covered:

| Finding | Disposition | Covered |
|---|---|---|
| F1 — OCS/extrusion unresolved | confirmed defect | ✅ PR #13 (duplicated by #14) |
| F2 — fit-point spline empty geometry | confirmed defect | ✅ PR #11 |
| F3 — rational weights discarded | confirmed defect | ✅ PR #11 |
| F4 — knot vectors discarded | confirmed defect | ✅ PR #11 |
| F5 — elevation dropped on **both** 2D polyline paths | undocumented limitation | ⚠️ **partial** — LWPOLYLINE only |
| F6 — source handle not recoverable | undocumented limitation | ❌ not addressed |
| F7 — `MISSING_LAYER` declared but never emitted | confirmed defect | ❌ not addressed |
| F8 — docs claim loss is never silent | derivative | ⚠️ partial |
| F9 — LWPOLYLINE vertices carry `numpy.float64` | confirmed defect | ❌ not addressed |
| F10 — periodic spline state | **unable to determine** | n/a — no claim to remediate |

An earlier revision of this notice said "eight findings" and omitted F9 and F10.
That undercounted the audit and is corrected here; the live coverage record is in
[`dev_orders/LEDGER.md`](dev_orders/LEDGER.md).

**F5 additionally repeats an analytical error the audit had already
corrected.** The remediation's characterization asserted an asymmetry between
the LWPOLYLINE and POLYLINE paths. The audit's probe P8c disproves that: a
**2D** POLYLINE drops the elevation attribute exactly as LWPOLYLINE does, and
the apparent asymmetry was an artifact of comparing against a **3D** polyline,
which carries Z in its vertices rather than in an attribute. The remediation's
fixture `polyline_elevated.dxf` uses `add_polyline3d` and reproduces that error;
PR #13 fixes elevation for LWPOLYLINE only, leaving 2D POLYLINE unfixed.

The completion claim in `GEOMETRY_IMPORT.md` was corrected under CS-REC-02 to
cover only the defects verified in-repository. F5 (completion), F6, and F7
remain open and require their own orders.

---

## 5. Recovery strategy

1. **CS-REC-01** — this notice.
2. **CS-REC-02** — scope completion claims to demonstrated evidence. *Done.*
3. **CS-REC-03** — retire ambiguous identifiers; see
   [`dev_orders/LEDGER.md`](dev_orders/LEDGER.md). Merged history is **not**
   renumbered; retirement is recorded instead, so Git history stays stable.
4. **CS-REC-04** — dev-order ledger with mandatory provenance headers.
5. **CS-REC-05** — [`GOVERNANCE/CROSS_REPOSITORY_BOUNDARIES.md`](GOVERNANCE/CROSS_REPOSITORY_BOUNDARIES.md).

**No production code changed under CS-REC-01…05.** Recovery is governance and
documentation only; the verified engineering is preserved intact.

### Deferred to a properly rooted session

CAM-Assist-Blueprint recovery must **not** run from a CAM-Creation-Studio
session. Executing cross-repository work from the wrong root is the mechanism
that caused this. Blueprint's roadmap should be regenerated in a session rooted
at its own repository, from its own README, `docs/dev_orders/`, schemas, and
tests. This session made no commit, branch, or file write to Blueprint; there is
nothing to roll back there.

---

## 6. Future cross-repository operating rules

1. **Every dev order carries a provenance header** — repository, root, branch,
   parent artifact, authority, cross-repository dependencies. An order whose
   parent artifact is not in this repository's ledger is treated as misrouted
   until confirmed.
2. **Identifier namespaces never overlap and are never reused.** `CS-xxx` is
   CAM-Creation-Studio; `CAM-Axx` is CAM-Assist-Blueprint. A retired identifier
   is never reissued.
3. **Before declaring an artifact missing,** enumerate this repository's `main`,
   branches, and PR list. §4.1 exists because that step was skipped.
4. **Before opening an implementation PR,** list open PRs and remote branches to
   check that nobody is already doing the work. §4.2 exists because that step
   was skipped.
5. **Planning from another repository is never authoritative** without
   repository-local confirmation.
6. **Verify before flagging.** Claims in a suspected-misrouted order are often
   checkable against the repository, and a check resolves provenance faster than
   argument. Two such claims were checked during this incident: one was
   confirmed as fact, the other disproved.
