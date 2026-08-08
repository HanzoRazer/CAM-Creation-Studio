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
| CS-008 REM 1/3 | Import loss evidence + characterization | CS-008R (unseen at the time) | `cs-008-import-evidence` | **Open, blocked** (#10) | — | Diagnostic fields |
| CS-008 REM 2/3 | Spline fidelity | as above | `cs-008-spline-fidelity` | **Open, blocked** (#11) | — | `Spline2D` extended |
| CS-008 REM 3/3 | Coordinate correctness | as above | `cs-008-coordinate-correctness` | **Closed — superseded** (#13) | **#14** | — (not merged) |
| CS-008R F1 | OCS→WCS on import | `docs/audits/CS-008_REAUDIT.md` | `cs-008-f1-coordinate-correctness` | Merged (#14) `c60009c` | — | Coordinates corrected |
| CS-008R F1-H | Post-F1 OCS hardening | `docs/audits/CS-008_REAUDIT.md` | `cs-008r-ocs-completeness` | **Open** (#16) | — | Diagnostic split: `NON_PLANAR_GEOMETRY` |
| CAM-CS-02 *(2nd)* | Shared fret-math extraction study | CAM-CS-01 audit §7 | — | **Retired identifier; unissued** | CS-010 | Cross-repository |
| CS-REC-01…05 | Session integrity recovery | This ledger | `cs-rec-governance` | **Open** (#15) | — | Governance only |

*Status column last refreshed 2026-08-08.* Confirm against GitHub before relying
on it — see § Source of truth.

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

## Coverage record — `docs/audits/CS-008_REAUDIT.md`

The audit declares **ten** findings, F1–F10. All ten are listed; none is omitted
because it is unremediated or undeterminable.

| Finding | Status |
|---------|--------|
| **F1** — OCS/extrusion unresolved | **Remediated.** #14, merged `c60009c`. Hardened by #16 (below). |
| **F2** — fit-point spline empty geometry | Represented by **#11**, subject to rebase + re-evaluation |
| **F3** — rational weights discarded | as F2 |
| **F4** — knot vectors discarded | as F2 |
| **F5** — elevation dropped | **NOT complete.** LWPOLYLINE is one case; **2D POLYLINE is equally affected.** The previously claimed LWPOLYLINE/POLYLINE asymmetry is **withdrawn** — it was an artifact of using POLYLINE3D as the control fixture (audit probe P8c). |
| **F6** — source handle not recoverable | Unremediated |
| **F7** — `MISSING_LAYER` never emitted | Unremediated |
| **F8** — docs claim loss is never silent | Partially addressed under CS-REC-02 (completion claims scoped to demonstrated evidence) |
| **F9** — LWPOLYLINE vertices carry `numpy.float64` | Unremediated |
| **F10** — periodic spline state | **Unable to determine.** No claim to remediate; re-probe before treating as either defect or non-defect. |

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

## Next orders (sequenced)

1. **#16** — post-F1 hardening. Open; closes a live regression on `main`.
2. **Rebase #10/#11** on corrected `main` and re-evaluate them **against the
   audit**, not against their stacked form. Their existing shape is not
   authoritative: it was built before the audit was located.
3. **New order — importer evidence completeness (F5/F6/F7).** Covers LWPOLYLINE
   *and* 2D POLYLINE elevation, handle traceability, and the missing-layer
   diagnostic. **Parent artifact: `docs/audits/CS-008_REAUDIT.md`** — explicitly
   not the earlier conversational remediation plan.
4. **Unissued:** F9 numeric normalization; F10 re-probe; CI enforcement of this
   ledger's mechanical rules (see § Enforcement status).

Remaining findings are deliberately **not** combined into a single sweep.
