# CAM-CS-01 — Authority Collision Audit

**Status:** Increment 1 deliverable (documentation and evidence only)
**Evidence commit (CAM-Creation-Studio):** `0442feb06e62944a58195af2a23a0151e37b05d9`
**Evidence commit (luthiers-toolbox):** `ffd155e436be89c15cdb0b83a96dc7d2cbefa251`

This document records, for each manufacturing capability CAM-CS-01 proposed to
build in CNC Creation Studio, whether an incumbent implementation already exists
— and where. It is an inventory, not a decision. No Toolbox file was modified.

> **Evidence freshness.** Last verified 2026-08-04 against the commits above.
> This inventories an **external repository at one commit**. The Luthiers
> Toolbox evolves independently, so file counts, paths, module sizes, and
> authority classifications here can go stale without anything in this
> repository changing. Re-verify before acting on a specific row.
>
> **Reading the columns.** *Toolbox Incumbent*, *CS Incumbent*, and *Current
> Authority Evidence* are **observed**. *Duplication Risk* is **inference**.
> *Recommended Disposition* is a **proposal for review**, not policy — policy
> lives only in
> [`CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md) §7.
> That document was ratified on 2026-08-05, but ratification approved its §7
> prohibitions and this investigation record — **not** the dispositions in this
> table. A row reading `REUSE` or `EXTRACT_SHARED` is still a recommendation
> awaiting its own increment.

All Toolbox paths below are relative to `services/api/` unless stated otherwise.

---

## 1. Scale of the incumbent

| Measure | Value |
| --- | --- |
| `services/api/app/cam/` Python files | **320** |
| `services/api/app/cam/` total source | **~2.9 MB** |
| `app/cam/` subpackages | 23 — `archtop`, `binding`, `carving`, `drilling`, `fhole`, `flying_v`, `headstock`, `neck`, `pocketing`, `profiling`, `rosette`, `routers`, `runtime`, `runtime_admission`, `runtime_capabilities`, `runtime_manifest`, `runtime_provenance`, `runtime_service`, `topology_builder`, `topology_validation`, `translators`, `vcarve` |
| Fret-related Python modules (repo-wide, excluding `.venv`/`__pycache__`) | **37** |
| CAM-Creation-Studio Python files (total) | **62** source + 30 test |

CNC Creation Studio is not entering an unoccupied manufacturing-platform role.

---

## 2. Authority classifications used

Per Ruling 3. Assigned only where evidence supports it; otherwise `UNKNOWN`.

`AUTHORITATIVE` · `PRODUCTION_INCUMBENT` · `ACTIVE_BUT_NONCANONICAL` ·
`EXPERIMENTAL` · `LEGACY` · `DUPLICATE` · `ADAPTER` · `ROUTER_ONLY` ·
`DEPRECATED` · `UNKNOWN`

### Evidence hierarchy applied

1. Executed tests and observable production behavior
2. Explicit authority or registry declarations
3. Active call paths
4. Schemas and contracts
5. Implementation code
6. Documentation
7. Product descriptions
8. Assumptions

Where documentation and implementation disagree, implementation was recorded and
the disagreement noted as an open question. Two such disagreements were found
(§4.1 and §6).

---

## 3. Path corrections to the ruling's candidate set

The ruling's candidate paths were partly inaccurate. Actual locations:

| Ruling path | Actual path | Size |
| --- | --- | --- |
| `app/cam/fret_slots_cam.py` | `app/calculators/fret_slots_cam.py` | 22,367 B |
| `app/cam/fret_slots_export.py` | `app/calculators/fret_slots_export.py` | 15,640 B |
| `app/cam/fret_slots_fan_cam.py` | `app/calculators/fret_slots_fan_cam.py` | 7,170 B |
| `app/cam/neck/fret_slots.py` | `app/cam/neck/fret_slots.py` ✓ | 8,737 B |
| `app/cam/fret_math.py` | `app/instrument_geometry/neck/fret_math.py` (20,081 B) **and** `app/api_v1/fret_math.py` (9,791 B) | two files |
| `app/cam/fretboard_geometry.py` | `app/instrument_geometry/body/fretboard_geometry.py` | 8,133 B |

Additional modules in the same subject area, not named by the ruling:

`app/instrument_geometry/neck/fretboard_ecosphere.py` (30,955 B) ·
`app/instrument_geometry/neck/fretboard_presets.py` ·
`app/instrument_geometry/fan_fret_guard.py` ·
`app/cam/fret_slots_from_ecosphere.py` ·
`app/cam/routers/fret_slots_router.py` ·
`app/rmos/fret_cam_guard.py` ·
`app/schemas/cam_fret_slots.py` · `app/schemas/cam_fret_slots_export.py` ·
`app/routers/instrument_geometry/nut_fret_router.py` ·
`app/routers/instrument/fretwork_router.py`

---

## 4. Collision table

| Capability | Proposed CS Responsibility | Toolbox Incumbent | CS Incumbent | Current Authority Evidence | Duplication Risk | Recommended Disposition | Open Question |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Fret position math** | `workflows/fretboard/fret_layout.py` | `instrument_geometry/neck/fret_math.py` → `compute_fret_positions_mm`, `SEMITONE_RATIO`, `perpendicular_distance_for_fret` | none | **Tier 1** — `tests/test_golden_fret_positions.py` asserts golden values for 4 scales plus determinism/monotonicity/half-scale invariants. 8+ importers. | **Critical** | `REUSE` or `EXTRACT_SHARED` | Which of the three implementations (§4.1) is the intended one? |
| **Multiscale / fan-fret geometry** | `fret_layout.calculate_multiscale_fret_lines` | `instrument_geometry/neck/fret_math.py` (FretFind2D PD parity, `PERP_ANGLE_EPS`); `instrument_geometry/fan_fret_guard.py`; `calculators/fret_slots_fan_cam.py` | none | Tier 1 — `app/tests/test_fan_fret_perpendicular.py`, `tests/cam/test_fan_fret_preview_normalization.py` | **Critical** | `REUSE` | Is FretFind2D the accepted parity target? |
| **Fretboard outline / taper / width** | `workflows/fretboard/geometry.py` | `instrument_geometry/body/fretboard_geometry.py` → `compute_fretboard_outline`, `compute_width_at_position_mm`, `compute_fret_slot_lines` | none | Tier 1 — `app/tests/instrument_geometry/test_instrument_geometry.py`; imported by both CAM calculators | High | `REUSE` or `EXTRACT_SHARED` | — |
| **Canonical fretboard document** | `contracts/design_intent.py` | `instrument_geometry/neck/fretboard_ecosphere.py` — self-declared *"single source of truth"*, Pydantic-validated, immutable after `compute()`, exports DXF/SVG/Scala | none | **Tier 2** explicit declaration + Tier 1 `tests/test_fretboard_ecosphere.py`, `app/tests/integration/test_fretboard_ecosphere_roundtrip.py` | **Critical** | `REUSE` as the design-intent contract | Is Ecosphere the intended cross-repository design-intent export? It is Pydantic; CS is dataclass-only. |
| **Fret-slot CAM / toolpaths** | `strategies/fret_slots.py` | `calculators/fret_slots_cam.py` → `generate_fret_slot_toolpaths`, `compute_cam_statistics`, `FretSlotToolpath` | none | Tier 1 — 4 test modules; Tier 3 — called by `cam/routers/fret_slots_router.py`, `cam/fret_slots_from_ecosphere.py` | **Critical** | `REUSE` / `ADAPT` | — |
| **Fret-slot G-code export** | `posts/*` + `application/export.py` | `calculators/fret_slots_export.py` — post-processor templates | `gcode/generator.py` (generic) | Tier 1 — `app/tests/test_cam_fret_slots_export.py`, `tests/test_fret_slots_intonation_model.py`; Tier 4 — `schemas/cam_fret_slots.py` | High | `RETAIN_IN_TOOLBOX` pending boundary decision | — |
| **Controller post-processors** | `posts/grbl.py`, `mach3.py`, `mach4.py`, `linuxcnc.py`, `marlin.py` | `schemas/cam_fret_slots.PostProcessor` enum declares **GRBL, Mach3, Mach4, LinuxCNC, PathPilot, MASSO, Fanuc, Haas**; `cam/post_processor.py` implements G43/G41/G42, tool-change sequencing, dialect support for GRBL/Mach3/Haas/LinuxCNC | `gcode/dialects.py` — 3 dialects: `marlin`, `genericCnc`, `laserGrbl` | Tier 4 (declared enum) + Tier 5 (implementation) | **Critical** | `RETAIN_IN_TOOLBOX`; CS keeps educational starter dialects | CS naming a post `grbl.py` would breach `docs/product-scope.md`. See Ruling 4. |
| **Post/machine compatibility gate** | `safety/validate.py` | `cam/postprocessor_boundary.py` — CAM Dev Order 6C. Explicitly *"a report, not machine code"*; no G-code, no file output; GREEN / YELLOW / RED gate semantics | `safety/rules.py` (advisory strings, no gate) | Tier 2 — explicit boundary rule in module docstring | High | **`EXTRACT_SHARED` — strongest reuse candidate.** Its report-not-machine-code posture already matches CS's constitution. | Is 6C stable enough to extract? |
| **Machine profiles** | `machines/models.py` + JSON profiles | `cam/rosette/cnc/cnc_machine_profiles.py` (GRBL/FANUC, rosette-scoped); `saw_lab/machine_profile_resolver.py` | `feeds_speeds/machines.py` → `MachineProfile` (feeds-scoped) | Tier 5 | Medium | `UNKNOWN` — neither incumbent is component-neutral | Is there a canonical Toolbox machine profile, or is it per-subsystem? |
| **Tool definitions** | `tooling/models.py` | `routers/tooling/post_processor_router.py`; `data_registry.Registry` | `feeds_speeds/tools.py` → `Tool` | Tier 5 | Medium | `UNKNOWN` | Where does the Toolbox tool library actually live? |
| **Safety validation / policy** | `safety/validate.py`, `policies.py` | `cam/rosette/cnc/cnc_safety_validator.py` (rosette-scoped); `rmos/policies/safety_policy.py`; `rmos/policies/saw_safety_gate.py`; `rmos/fret_cam_guard.py`; `api_v1/rmos_safety.py`; `core/safety.py` (`safety_critical` decorator) | `safety/rules.py` | Tier 1 — `app/tests/rmos/test_safety_policy.py`, `test_saw_safety_gate.py` | High | `RETAIN_IN_TOOLBOX` | RMOS looks like the general policy layer; is it the intended one? |
| **Simulation** | `simulation/**` | `util/gcode/simulator.py` (25,787 B) — modal state machine, canned-cycle expansion, G17/18/19 arcs, backplot segments, warnings; consolidated simulation routers | `preview/toolpath_model.py` — preview model only | Tier 2 — documented fidelity audit (TOOLPATH_ANIMATION_AUDIT 2026-05-30) + Tier 5 | High | `RETAIN_IN_TOOLBOX` | `docs/product-scope.md` forbids CS claiming simulation at all. |
| **SVG / inlay intake** | `geometry/svg_import.py`, `strategies/inlays.py` | `art_studio/services/generators/inlay_geometry_svg.py` (15,473 B), `inlay_import.py` (15,198 B), `inlay_geometry_{core,bezier,rope,bom,transforms}.py`, `inlay_primitives.py`, `inlay_patterns.py` (21,775 B), `_inlay_gcode_addon.py` | `geometry/` — **DXF only** | Tier 5 + Tier 3 (`inlay_router.py`) | **Critical** | `REUSE` / `EXTRACT_SHARED` | — |
| **Male plugs / matching parts** | `strategies/plugs.py` | `calculators/inlay_calc.py`; `art_studio/services/generators/inlay_export.py` | none | Tier 5 | High | `UNKNOWN` — plug/pocket compensation not yet located | Does the Toolbox generate male plugs today? |
| **Holding tabs** | `strategies/holding_tabs.py` | Not located | none | — | Low | `UNKNOWN` | Genuine gap candidate. |
| **Stock flattening / surfacing** | `strategies/stock_flattening.py` | `cam/pocketing/`, `cam/profiling/profile_toolpath.py`, `cam/carving/` | none | Tier 5 | Medium | `UNKNOWN` — not traced in this increment | — |
| **Radius / compound-radius surfacing** | `strategies/radius_surface.py` | `cam/neck/profile_carving.py`; compound radius referenced in `cam/neck/fret_slots.py` | none | Tier 5 | Medium | `UNKNOWN` | — |
| **Runtime admission** | not proposed | `cam/runtime_admission/`, `runtime_capabilities/`, `runtime_manifest/`, `runtime_service/` | none | Tier 5 | — | `RETAIN_IN_TOOLBOX` | CS has no analogue; may already solve the job-manifest problem. |
| **Runtime provenance** | `artifacts/manifest.py` | `cam/runtime_provenance/` | none | Tier 5 | Medium | `RETAIN_IN_TOOLBOX` | Does it already carry source hash/revision? |
| **Topology validation** | `workflows/fretboard/validation.py` | `cam/topology_validation/`, `cam/topology_builder/` | none | Tier 5 | Medium | `UNKNOWN` | — |
| **Output packaging / artifacts** | `artifacts/**` | `cam/runtime_manifest/`; `art_studio/.../inlay_export.py` | none | Tier 5 | Medium | `UNKNOWN` | — |
| **Operation planning / sequencing** | `workflows/fretboard/planner.py` | `cam/neck/orchestrator.py` (`NeckPipeline`) | none | Tier 1 — `tests/test_neck_cnc_pipeline.py` | High | `REUSE` as prior art | — |
| **Guided authoring UX** | Tranche 9 | Web client under `packages/client` | `app/`, `src/`, `cli/` | Tier 5 | **Low** | **Genuine CS differentiator** | See product boundary doc. |
| **G-code education / teaching** | not proposed | not located | `docs/gcode-basics.md`, `docs/quick-start.md`, validator explanations | Tier 2 — `docs/product-scope.md` | **None** | **Genuine CS differentiator** | — |
| **Offline / local operation** | Decision 1 | Toolbox is a FastAPI service + Docker + Railway | CS is a local package + CLI + static browser app | Tier 5 | **None** | **Genuine CS differentiator** | — |

---

## 4.1 Finding — three independent fret-position implementations inside the Toolbox

| # | Location | Form | Status |
| --- | --- | --- | --- |
| 1 | `app/instrument_geometry/neck/fret_math.py` | `compute_fret_positions_mm`, `SEMITONE_RATIO = 2**(1/12)` | **AUTHORITATIVE** — golden tests, 8+ importers |
| 2 | `app/api_v1/fret_math.py` lines 117, 183 | inline `req.scale_length_mm * (1 - 2 ** (-n / 12))` inside FastAPI handlers | **DUPLICATE** (router-embedded) |
| 3 | `app/cam/neck/fret_slots.py` line 105 | inline `self.config.scale_length_mm * (1 - (1 / (2 ** (fret_number / 12))))` | **DUPLICATE** (pipeline-embedded) |

The three expressions are **mathematically identical** — `1 − 2^(−n/12)` and
`1 − 1/2^(n/12)` are the same value. This is duplicated *authority*, not
divergent *behavior*. No numerical discrepancy is claimed.

**Documentation/implementation disagreement:** `app/cam/neck/fret_slots.py` line 7
states *"Connects to existing fret_slots_cam.py calculator for position
calculations."* Its import list does not include `fret_slots_cam`, and it computes
positions inline at line 105. Per the evidence hierarchy, implementation is
recorded; the docstring is noted as stale. **This is a Toolbox-internal finding
and is out of scope to fix here** (§4.2 of the original order forbids changing
the Toolbox repository). Recorded for the Toolbox owner.

`app/cam/neck/fret_slots.py` is **not** orphaned — `FretSlotGenerator` is
exported from `app/cam/neck/__init__.py`, instantiated by
`app/cam/neck/orchestrator.py`, and exercised by `tests/test_neck_cnc_pipeline.py`.
Classification: **PRODUCTION_INCUMBENT with embedded duplicate math**.

---

## 5. Tier-1 evidence located: an executable fret-position oracle

`services/api/tests/test_golden_fret_positions.py` exercises
`app.instrument_geometry.neck.fret_math.compute_fret_positions_mm` against
pre-calculated golden fixtures.

| Fixture | Scale | Frets |
| --- | --- | --- |
| Fender | 647.7 mm (25.5") | 22 |
| Gibson | 628.65 mm (24.75") | 22 |
| PRS | 635.0 mm (25") | 24 |
| Bass | 863.6 mm (34") | 21 |

Plus invariant tests: monotonic increase, fret 12 = half scale, fret 24 = three
quarters scale, all positions < scale length, spacing decreases toward the
bridge, and determinism across repeated calls.

Spot-checked against the recorded values: Fender fret 1 = 36.3526 mm and fret 12
= 323.85 mm are consistent with `scale × (1 − 2^(−n/12))` measured from the nut.

**This is a real, runnable oracle** — unlike the standalone HTML application,
which was not located (see `CAM_CS_01_REFERENCE_ARTIFACT_SEARCH.md`). Per
Ruling 3 it is **not** thereby declared the parity oracle; it is recorded as the
strongest currently available implementation reference.

---

## 6. Finding — the original handoff's governing boundary does not describe reality

CAM-CS-01 §3 asserted that the Toolbox owns design and Creation Studio owns
"machining authoring, operation planning, toolpath generation, simulation,
post-processing."

Every one of those responsibilities has a Toolbox incumbent, most with tests:
toolpath generation (`cam/` — 320 files), operation planning
(`cam/neck/orchestrator.py`), simulation (`util/gcode/simulator.py`),
post-processing (`cam/post_processor.py`, 8 declared controllers), safety
(`rmos/policies/`, `cnc_safety_validator.py`).

The boundary in the original order is a **desired future state described as
present fact**. It is superseded by
[`CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md).

---

## 7. Open questions for architectural review

1. Is `fretboard_ecosphere.py` the intended cross-repository design-intent
   export? It is Pydantic; CS is dataclass-only by convention (Ruling 6). A
   shared contract would need a serialization boundary.
2. Which of the three fret-position implementations is intended to survive, and
   is consolidation a Toolbox task rather than a CAM-CS-01 task?
3. Is `postprocessor_boundary.py` (6C) stable enough to extract as the shared
   preflight package? Its posture already matches CS's constitution.
4. Does a canonical, component-neutral machine profile exist in the Toolbox, or
   is it per-subsystem (`rosette`, `saw_lab`)?
5. Does `cam/runtime_provenance/` already satisfy the provenance requirement
   CAM-CS-01 assigned to `artifacts/manifest.py`?
6. Are holding tabs and male-plug compensation genuine gaps? They are the only
   fretboard capabilities for which no incumbent was located.
7. What is the intended long-term relationship — is the Toolbox's `app/cam/`
   staying, or is it a migration source?
