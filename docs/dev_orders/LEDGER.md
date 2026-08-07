# Dev-Order Ledger — CAM-Creation-Studio

**Order:** CS-REC-04 · **Scope:** this repository only.

Every development order accepted by CAM-Creation-Studio is indexed here. The
ledger exists so a misrouted order is detectable **on arrival** rather than
several exchanges later: an order whose *Parent Artifact* is not listed below,
or whose *Repository* is not this one, is treated as misrouted until confirmed.

See [`../SESSION_INTEGRITY_2026-08-07.md`](../SESSION_INTEGRITY_2026-08-07.md)
for the incident that motivated this.

---

## Mandatory provenance header

Every dev order must open with:

```text
Repository:                CAM-Creation-Studio
Repository Root:           HanzoRazer/CAM-Creation-Studio
Repository Branch:         main
Parent Artifact:           docs/audits/CS-008_REAUDIT.md
Authority:                 Repository documentation
Generated:                 2026-08-07
Cross Repository Deps:     None
```

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
| CS-009 | Export preflight gate | `EXPORT_PREFLIGHT_SEMANTICS.md` | `cs-009-export-preflight` | Merged (#9) | — | Export gate; no machine-readiness claim |
| CS-008R | Geometry import conformance re-audit | — | `cs-008r-conformance-reaudit` | Merged (#12) | — | Evidence only |
| CS-008 REM 1/3 | Import loss evidence + characterization | CS-008R (unseen at the time) | `cs-008-import-evidence` | **Open, blocked** (#10) | — | Diagnostic fields |
| CS-008 REM 2/3 | Spline fidelity | as above | `cs-008-spline-fidelity` | **Open, blocked** (#11) | — | `Spline2D` extended |
| CS-008 REM 3/3 | Coordinate correctness | as above | `cs-008-coordinate-correctness` | **Closed — superseded** (#13) | **#14** | — (not merged) |
| CS-008R F1 | OCS→WCS on import | `CS-008_REAUDIT.md` | `cs-008-f1-coordinate-correctness` | **Open — canonical F1** (#14) | — | Coordinates corrected |
| CAM-CS-02 *(2nd)* | Shared fret-math extraction study | CAM-CS-01 audit §7 | — | **Retired identifier; unissued** | CS-010 | Cross-repository |
| CS-REC-01…05 | Session integrity recovery | This ledger | `cs-rec-governance` | **Open** | — | Governance only |

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

## Coverage record — `docs/audits/CS-008_REAUDIT.md`

| Finding | Status |
|---------|--------|
| **F1** — OCS/extrusion unresolved | Addressed by **#14** (pending review) |
| **F2** — fit-point spline empty geometry | Represented by **#11**, subject to rebase + re-evaluation |
| **F3** — rational weights discarded | as F2 |
| **F4** — knot vectors discarded | as F2 |
| **F5** — elevation dropped | **NOT complete.** LWPOLYLINE is one case; **2D POLYLINE is equally affected.** The previously claimed LWPOLYLINE/POLYLINE asymmetry is **withdrawn** — it was an artifact of using POLYLINE3D as the control fixture (audit probe P8c). |
| **F6** — source handle not recoverable | Unremediated |
| **F7** — `MISSING_LAYER` never emitted | Unremediated |

## Next orders (sequenced)

1. **After #14 merges** — rebase #10/#11 on corrected `main` and re-evaluate them
   **against the audit**, not against their stacked form. Their existing shape is
   not authoritative: it was built before the audit was located.
2. **New order — importer evidence completeness (F5/F6/F7).** Covers LWPOLYLINE
   *and* 2D POLYLINE elevation, handle traceability, and the missing-layer
   diagnostic. **Parent artifact: `docs/audits/CS-008_REAUDIT.md`** — explicitly
   not the earlier conversational remediation plan.

Remaining findings are deliberately **not** combined into a single sweep.
