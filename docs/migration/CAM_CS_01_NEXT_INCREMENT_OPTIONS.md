# CAM-CS-01 — Next Increment Options

**Status:** Increment 1 deliverable. Options for architectural review.
**Decision required before Increment 2 begins.**

Per Ruling 5 §7, four options are presented. The recommendation at the end is
grounded in the completed audit, not architectural preference.

Prerequisite reading:
[`CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md`](CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md) ·
[`FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md`](FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md) ·
[`../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md)

---

## Option A — Creation Studio adapter

Consume an existing canonical Toolbox contract without duplicating algorithms.
Concretely: Creation Studio reads a `FretboardEcosphere` export
(`services/api/app/instrument_geometry/neck/fretboard_ecosphere.py`) as
read-only design intent, preserving source identifier, revision, and hash.

| | |
| --- | --- |
| **Prerequisite evidence** | Is Ecosphere a stable, versioned, exportable contract, or an internal model? Does it have a serialization format intended for external consumers? `UNKNOWN`. |
| **Affected repositories** | Creation Studio only (read-only consumption). Toolbox unchanged. |
| **Duplication risk** | **Low** — no algorithm is copied. |
| **Authority result** | Toolbox retains design authority. Creation Studio gains a provenance-preserving intake. |
| **Estimated migration surface** | Small: an intake contract, a provenance record, validation of version/staleness. No CAM code. |
| **Reversibility** | **High** — an intake adapter can be deleted without consequence. |
| **Recommended next proof** | Round-trip a real Ecosphere export into a Creation Studio intake record and assert that no field is silently altered. |
| **Risk** | Ecosphere is Pydantic; Creation Studio is dataclass-only (Ruling 6). A serialization boundary is required — Creation Studio must consume JSON, not import the Pydantic model. |

---

## Option B — Shared-package extraction

Extract one narrowly bounded incumbent capability into a repository-neutral
Python package that both repositories consume. Authority moves to the package; it
does not fork.

Ranked candidates from the audit:

| Rank | Candidate | Why | Blocker |
| --- | --- | --- | --- |
| 1 | Fret position mathematics — `instrument_geometry/neck/fret_math.py` | Pure, deterministic, no I/O, no framework dependencies, golden-test-backed with fixtures for four scale lengths | Three call sites duplicate it (audit §4.1); consolidation is a Toolbox task |
| 2 | Export preflight — `cam/postprocessor_boundary.py` | Its declared posture already matches Creation Studio's constitution: report-not-machine-code, GREEN/YELLOW/RED | Stability of CAM Dev Order 6C is `UNKNOWN` |
| 3 | Fretboard geometry — `instrument_geometry/body/fretboard_geometry.py` | Small, pure, depends only on fret math | Depends on `neck_profiles.FretboardSpec` |
| 4 | SVG intake — `art_studio/.../inlay_geometry_svg.py`, `inlay_import.py` | Creation Studio has DXF only; SVG is a real gap | Large surface, tangled with pattern generation |

| | |
| --- | --- |
| **Prerequisite evidence** | Toolbox owner agreement that the capability may move. Confirmation that no Pydantic/FastAPI/RMOS dependency crosses the boundary. |
| **Affected repositories** | **Both**, plus a new shared package. |
| **Duplication risk** | **Lowest of any option** — extraction removes duplication rather than adding it. |
| **Authority result** | Single authority in the shared package; both products become consumers. |
| **Estimated migration surface** | Candidate 1: small (one module, one test file, ~8 importers to repoint). Candidate 4: large. |
| **Reversibility** | **Medium** — a published package with two consumers is harder to unwind than an adapter. |
| **Recommended next proof** | Extract candidate 1 only. Port `tests/test_golden_fret_positions.py` verbatim as the package's own suite. Repoint one Toolbox consumer. Prove Creation Studio can consume it without Pydantic. |
| **Risk** | Requires cross-repository coordination, which §4.2 of the original order placed out of scope. Needs explicit authorization. |

---

## Option C — Creation Studio-native capability

Implement only a capability demonstrated absent from the Toolbox and consistent
with `docs/product-scope.md`.

Candidates the audit found **no incumbent** for:

| Candidate | Evidence of absence | Scope fit |
| --- | --- | --- |
| **Holding-tab generation** | Not located in either repository | Toolpath strategy — borderline against product scope |
| **Male-plug / pocket compensation** | Not located; `inlay_calc.py` and `inlay_export.py` not traced to plug compensation | Same |
| **Export preflight for CS's own dialects** | `safety/rules.py` is advisory strings only; there is no gate | **Strong fit** — see `EXPORT_PREFLIGHT_SEMANTICS.md` |
| **SVG intake for CS** | `geometry/` is DXF-only | Fits, but duplicates Toolbox SVG work → prefer Option B candidate 4 |
| **Guided offline authoring UX** | No offline Toolbox equivalent (FastAPI service) | **Strong fit** — the clearest distinctive role |

| | |
| --- | --- |
| **Prerequisite evidence** | Proof of absence, not merely failure to find. Holding tabs and plugs are currently `UNKNOWN`, not confirmed gaps — one more tracing pass is needed. |
| **Affected repositories** | Creation Studio only. |
| **Duplication risk** | **Low if the gap is real; high if the search was incomplete.** |
| **Authority result** | Creation Studio gains genuine authority over something no one else owns. |
| **Estimated migration surface** | Small and self-contained. |
| **Reversibility** | **High.** |
| **Recommended next proof** | For export preflight: implement `ExportPreflightResult` over the existing `gcode/validator/` findings and the three existing dialects. No fretboard content, no new registries, ~1 module + 1 test module. |
| **Risk** | Choosing holding tabs or plugs before confirming absence would create exactly the duplication this study exists to prevent. |

---

## Option D — Cross-repository manufacturing migration

Define a staged program moving manufacturing authority from the Toolbox to
Creation Studio, including deprecation and consumer migration.

| | |
| --- | --- |
| **Prerequisite evidence** | A full inventory of `app/cam/` (320 files, ~2.9 MB, 23 subpackages) — this increment traced only the fretboard subset. Consumer maps for every module. Approved replacement contracts. A parity method. |
| **Affected repositories** | **Both**, plus every Toolbox API consumer. |
| **Duplication risk** | **Highest** — during migration both implementations exist by definition. |
| **Authority result** | Eventually single, in Creation Studio. Transitionally split. |
| **Estimated migration surface** | **Very large.** 320 CAM files, 8 declared controller post-processors, RMOS policy layer, runtime admission/provenance/manifest, simulation, art-studio SVG and inlay stack, plus FastAPI routers and their clients. |
| **Reversibility** | **Low.** Once consumers migrate and incumbents are deprecated, reversal is another migration. |
| **Recommended next proof** | Do not start with code. Start with a consumer map of `app/cam/` and a written deprecation policy. |
| **Risk** | Creation Studio today is 62 source modules against the Toolbox's 320-file CAM package. Migration in this direction means the smaller, less mature system absorbs the larger one. That may still be right for product reasons, but it is a multi-quarter program with its own governance — not a fretboard order. |

---

## Comparison

| | A — Adapter | B — Shared package | C — CS-native | D — Migration |
| --- | --- | --- | --- | --- |
| Duplication risk | Low | Lowest | Low if gap real | Highest |
| Repositories touched | 1 | 2 + new | 1 | 2 + all consumers |
| Reversibility | High | Medium | High | Low |
| Surface | Small | Small (cand. 1) | Small | Very large |
| Needs Toolbox authorization | No | **Yes** | No | **Yes** |
| Blocked by open questions | Yes (1) | Yes (2, 3) | Partly (6) | Yes (all) |
| Proves something about the boundary | Weakly | **Strongly** | Weakly | N/A |

Open-question numbers refer to `CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md` §7.

---

## Recommendation

**Sequence C-then-B, and do not start D.**

The audit supports this on evidence rather than preference:

1. **Increment 2 = Option C, export preflight only.** It is the single capability
   where Creation Studio has a confirmed absence (`safety/rules.py` is advisory
   strings with no gate), a constitutional mandate (Ruling 4 requires the
   terminology be settled before any export claim), and zero duplication risk —
   it operates over Creation Studio's own three dialects and its own validator
   findings. It touches one repository, needs no Toolbox authorization, is fully
   reversible, and is roughly one module plus one test module. It contains no
   fretboard content at all, which is appropriate: the fretboard question is not
   yet answerable.

2. **Increment 3 = Option B, candidate 1 (fret math) — if and only if
   cross-repository work is authorized.** This is the one action that would
   actually resolve the boundary question rather than working around it. Fret
   mathematics is the cleanest seam in either repository: pure, deterministic,
   framework-free, and already covered by golden fixtures for four scale lengths
   that can be ported verbatim as the shared package's acceptance suite. It also
   forces the Pydantic-versus-dataclass question to be answered concretely rather
   than in the abstract.

3. **Option A becomes worth doing after B**, because Ecosphere intake is far more
   valuable once the underlying math is shared than while it is forked.

4. **Option D should not begin.** Not because it is wrong, but because nothing in
   this increment produced the evidence it requires. Its prerequisite is a
   consumer map of 320 CAM modules; this study traced roughly a dozen.

### What would change this recommendation

- If cross-repository work is **not** authorized, Option B is unavailable and the
  honest path is C plus a documented statement that the boundary question remains
  open indefinitely.
- If holding tabs or male plugs are confirmed absent from the Toolbox by a second
  tracing pass, they become legitimate Option C candidates and the first real
  fretboard-shaped work Creation Studio could own without duplication.
- If the standalone HTML application is supplied, it changes the evidence
  available for the matrix — but per Ruling 1 it does not supersede canonical
  repository implementations, so it would not by itself change this ranking.

---

## Explicitly not recommended

- Any increment combining more than one extraction seam (Ruling 5, Increment 2).
- Any fretboard geometry, fret mathematics, toolpath strategy, controller post,
  simulation, or safety policy in Creation Studio before the boundary is settled.
- Any `REIMPLEMENT_WITH_JUSTIFICATION` disposition. None is assigned in the
  matrix, and none is justified by current evidence.
