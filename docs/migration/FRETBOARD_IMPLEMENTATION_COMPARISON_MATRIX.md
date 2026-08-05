# Fretboard Implementation Comparison Matrix

**Status:** Increment 1 deliverable — scaffold populated with verified findings
**Evidence commit (CAM-Creation-Studio):** `0442feb06e62944a58195af2a23a0151e37b05d9`
**Evidence commit (luthiers-toolbox):** `ffd155e436be89c15cdb0b83a96dc7d2cbefa251`

This replaces the binary HTML-versus-Python parity matrix specified in the
original CAM-CS-01 handoff. Per Ruling 3, a binary matrix cannot be built: the
standalone application was not located, and the Toolbox — not Creation Studio —
holds the incumbent implementations.

**Unknown cells are explicitly `UNKNOWN`. No cell has been filled by inference.**

---

## Vocabulary

### Toolbox authority status
`AUTHORITATIVE` · `PRODUCTION_INCUMBENT` · `ACTIVE_BUT_NONCANONICAL` ·
`EXPERIMENTAL` · `LEGACY` · `DUPLICATE` · `ADAPTER` · `ROUTER_ONLY` ·
`DEPRECATED` · `UNKNOWN`

### Migration disposition
`REUSE` · `EXTRACT_SHARED` · `ADAPT` · `WRAP` · `RETAIN_IN_TOOLBOX` ·
`MIGRATE_LATER` · `DEPRECATE_DUPLICATE` · `REIMPLEMENT_WITH_JUSTIFICATION` ·
`DESCRIBED_NOT_OBSERVED` · `UNKNOWN`

`REIMPLEMENT_WITH_JUSTIFICATION` is not assigned anywhere in this document. It
requires explicit approval plus documented evidence that reuse, extraction, and
adaptation are all unsuitable — evidence this increment did not produce.

### Standalone artifact evidence
Every row reads `NOT_LOCATED`. See
[`CAM_CS_01_REFERENCE_ARTIFACT_SEARCH.md`](CAM_CS_01_REFERENCE_ARTIFACT_SEARCH.md).

Toolbox paths are relative to `services/api/`. CS paths are relative to
`python/cam_creation_studio/`.

---

## A. Fret layout and geometry

| Capability | Declared standalone behavior | Standalone artifact evidence | Toolbox incumbent | Toolbox authority status | CS existing capability | Behavioral tests | Observed differences | Recommended authority | Migration disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equal-temperament fret positions | 12-TET positions from scale length | `NOT_LOCATED` | `instrument_geometry/neck/fret_math.py` → `compute_fret_positions_mm` | `AUTHORITATIVE` | none | `tests/test_golden_fret_positions.py` — golden values for 4 scales + monotonicity, half-scale, three-quarter-scale, determinism | none observable (no standalone to compare) | Toolbox | `REUSE` |
| — same, router copy | — | `NOT_LOCATED` | `api_v1/fret_math.py` L117, L183 — inline `scale*(1-2**(-n/12))` | `DUPLICATE` (router-embedded) | none | none direct | mathematically identical to authority | Toolbox (consolidate) | `DEPRECATE_DUPLICATE` |
| — same, neck-pipeline copy | — | `NOT_LOCATED` | `cam/neck/fret_slots.py` L105 — inline `scale*(1-(1/(2**(n/12))))` | `PRODUCTION_INCUMBENT` with embedded `DUPLICATE` math | none | `tests/test_neck_cnc_pipeline.py` | mathematically identical; docstring claims delegation that the imports do not show | Toolbox (consolidate) | `DEPRECATE_DUPLICATE` |
| Rule of 18 (divisor 17.817 / 18.0 / other) | named as an alternate fret-placement method | `NOT_LOCATED` | not located — `calculators/alternative_temperaments.py` provides ratio sets and n-TET, not Rule of 18 | `UNKNOWN` | none | `app/tests/calculators/test_alternative_temperaments_ntet.py` | — | `UNKNOWN` | `DESCRIBED_NOT_OBSERVED` |
| Multiscale / fan-fret lines | fan-fret geometry with a perpendicular fret | `NOT_LOCATED` | `instrument_geometry/neck/fret_math.py` (`perpendicular_distance_for_fret`, `PERP_ANGLE_EPS`, FretFind2D PD parity); `calculators/fret_slots_fan_cam.py`; `instrument_geometry/fan_fret_guard.py` | `AUTHORITATIVE` | none | `app/tests/test_fan_fret_perpendicular.py`, `tests/cam/test_fan_fret_preview_normalization.py` | — | Toolbox | `REUSE` |
| Perpendicular-fret reference location | "the reference location used by the HTML app" | `NOT_LOCATED` | FretFind2D convention: PD = 1 − 2^(−n/12), fret 12 → 0.5 (documented default) | `AUTHORITATIVE` | none | as above | reference location unknowable without the standalone | Toolbox | `DESCRIBED_NOT_OBSERVED` for the claimed HTML default; `REUSE` for the Toolbox convention |
| Fretboard outline / taper / width at position | tapered and rectangular planforms | `NOT_LOCATED` | `instrument_geometry/body/fretboard_geometry.py` → `compute_fretboard_outline`, `compute_width_at_position_mm`, `compute_fret_slot_lines` | `AUTHORITATIVE` | none | `app/tests/instrument_geometry/test_instrument_geometry.py` | — | Toolbox | `REUSE` |
| Heel width from nut width + string spacing | derived heel calculation | `NOT_LOCATED` | `UNKNOWN` — not traced | `UNKNOWN` | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Canonical fretboard document / design intent | implied by the design-intent contract | `NOT_LOCATED` | `instrument_geometry/neck/fretboard_ecosphere.py` — self-declared single source of truth; Pydantic; immutable after `compute()`; DXF/SVG/Scala export | `AUTHORITATIVE` (explicit declaration, tier 2) | none | `tests/test_fretboard_ecosphere.py`, `app/tests/integration/test_fretboard_ecosphere_roundtrip.py` | — | Toolbox | `REUSE` — candidate design-intent contract |
| Fretboard presets | standard scale presets | `NOT_LOCATED` | `instrument_geometry/neck/fretboard_presets.py` | `PRODUCTION_INCUMBENT` | none | `UNKNOWN` | — | Toolbox | `REUSE` |
| Constant radius | constant-radius board | `NOT_LOCATED` | referenced in `cam/neck/fret_slots.py` and `cam/neck/profile_carving.py` | `UNKNOWN` — not traced to an authority | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Compound radius | nut radius ≠ heel radius, interpolated | `NOT_LOCATED` | `fretboard_ecosphere.py` documents "compound radius profiles"; `cam/neck/fret_slots.py` documents station-aware depths | `UNKNOWN` — declared, not traced | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Zero fret / nut slot references | mutually exclusive options, slot offsets | `NOT_LOCATED` | `routers/instrument_geometry/nut_fret_router.py`; `calculators/nut_slot_calc.py` | `UNKNOWN` | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |

---

## B. Machining strategies

| Capability | Declared standalone behavior | Standalone artifact evidence | Toolbox incumbent | Toolbox authority status | CS existing capability | Behavioral tests | Observed differences | Recommended authority | Migration disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fret-slot toolpath generation | flat slots, depth passes, overtravel, retracts | `NOT_LOCATED` | `calculators/fret_slots_cam.py` → `generate_fret_slot_toolpaths`, `compute_cam_statistics`, `FretSlotToolpath` | `PRODUCTION_INCUMBENT` | none | `app/tests/calculators/test_fret_slots_cam_guard.py`, `tests/cam/test_fret_slots_preview_normalization.py`, `tests/test_cam_fret_slots_preview_smoke.py` | — | Toolbox | `REUSE` / `ADAPT` |
| Fan-fret slot toolpaths | angled slots | `NOT_LOCATED` | `calculators/fret_slots_fan_cam.py` → `generate_fan_fret_cam` | `PRODUCTION_INCUMBENT` | none | `tests/cam/test_fan_fret_preview_normalization.py` | — | Toolbox | `REUSE` |
| Radiused fret slots | slot floor follows board radius | `NOT_LOCATED` | `cam/neck/fret_slots.py` — "compound radius support (depth varies across width)", station-aware depths | `PRODUCTION_INCUMBENT` | none | `tests/test_neck_cnc_pipeline.py` | — | Toolbox | `REUSE` |
| Fret slots from canonical document | — | `NOT_LOCATED` | `cam/fret_slots_from_ecosphere.py` | `PRODUCTION_INCUMBENT` (`ADAPTER` shape) | none | `tests/cam/test_fret_slots_from_ecosphere.py` | — | Toolbox | `REUSE` |
| Fret-slot CAM guard | validation of slot feasibility | `NOT_LOCATED` | `rmos/fret_cam_guard.py` — fan-fret geometry + cutting-physics guards → `RmosMessage[]` | `PRODUCTION_INCUMBENT` | none | `app/tests/calculators/test_fret_slots_cam_guard.py` | — | Toolbox | `REUSE` |
| Stock flattening / surfacing | boundary, stepover, entry, depth passes, finish pass | `NOT_LOCATED` | `cam/pocketing/`, `cam/profiling/profile_toolpath.py`, `cam/carving/` | `UNKNOWN` — not traced | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Radius-surface machining | raster/contour, stepover, finish pass, edge handling | `NOT_LOCATED` | `cam/neck/profile_carving.py` | `UNKNOWN` — not traced | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Position markers (dot, rect, square, oval) | pocket generation at standard and custom frets | `NOT_LOCATED` | `art_studio/.../inlay_primitives.py`, `inlay_patterns.py` | `UNKNOWN` — not traced for marker semantics | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Custom SVG markers | SVG-driven marker pockets | `NOT_LOCATED` | `art_studio/.../inlay_geometry_svg.py`, `inlay_import.py` | `PRODUCTION_INCUMBENT` | none — CS imports DXF only | `UNKNOWN` | — | Toolbox | `REUSE` / `EXTRACT_SHARED` |
| Custom SVG inlay pockets | scale, rotate, translate, depth, tool compensation, open-path rejection | `NOT_LOCATED` | `art_studio/.../inlay_geometry_{core,bezier,rope,bom,transforms}.py`, `inlay_import.py`, `inlay_calc.py`, `_inlay_gcode_addon.py` | `PRODUCTION_INCUMBENT` | none | `UNKNOWN` | — | Toolbox | `REUSE` / `EXTRACT_SHARED` |
| Male plugs / matching parts | plug G-code + vector output, clearance compensation | `NOT_LOCATED` | `calculators/inlay_calc.py`, `art_studio/.../inlay_export.py` — plug/pocket compensation **not located** | `UNKNOWN` | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` — possible genuine gap |
| Holding tabs | count, width, height, placement, interference checks | `NOT_LOCATED` | **not located** | `UNKNOWN` | none | none | — | `UNKNOWN` | `UNKNOWN` — strongest genuine-gap candidate |
| Operation ordering / sequencing | dependencies, tool changes, grouping | `NOT_LOCATED` | `cam/neck/orchestrator.py` → `NeckPipeline` | `PRODUCTION_INCUMBENT` | none | `tests/test_neck_cnc_pipeline.py` | — | Toolbox | `REUSE` as prior art |

---

## C. Output, machine, and safety

| Capability | Declared standalone behavior | Standalone artifact evidence | Toolbox incumbent | Toolbox authority status | CS existing capability | Behavioral tests | Observed differences | Recommended authority | Migration disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Controller post-processors | GRBL, Marlin, LinuxCNC, Mach3, Mach4 presets | `NOT_LOCATED` | `schemas/cam_fret_slots.PostProcessor` declares GRBL, Mach3, Mach4, LinuxCNC, PathPilot, MASSO, Fanuc, Haas; `cam/post_processor.py` implements G43/G41/G42 + tool-change sequencing for GRBL/Mach3/Haas/LinuxCNC; `calculators/fret_slots_export.py` holds post templates | `PRODUCTION_INCUMBENT` (tier 4 declaration + tier 5 implementation) | `gcode/dialects.py` — 3 educational starter dialects: `marlin`, `genericCnc`, `laserGrbl` | `app/tests/test_cam_fret_slots_export.py`, `tests/test_fret_slots_intonation_model.py` | CS dialects are deliberately generic and non-certified; Toolbox posts are controller-named | Toolbox for controller-named posts | `RETAIN_IN_TOOLBOX` — CS naming a post `grbl.py` would breach `docs/product-scope.md` |
| Post/machine compatibility report | implied by the safety gate | `NOT_LOCATED` | `cam/postprocessor_boundary.py` — CAM Dev Order 6C; explicitly *"a report, not machine code"*; no G-code, no file output; GREEN / YELLOW / RED | `PRODUCTION_INCUMBENT`, explicit boundary declaration | `safety/rules.py` — advisory strings, **no gate** | `UNKNOWN` | posture already matches CS's constitution | shared package (candidate) | `EXTRACT_SHARED` — strongest reuse candidate |
| Machine profiles | travel envelope, spindle/laser capability, feed and RPM limits | `NOT_LOCATED` | `cam/rosette/cnc/cnc_machine_profiles.py` (GRBL/FANUC, rosette-scoped); `saw_lab/machine_profile_resolver.py` | `ACTIVE_BUT_NONCANONICAL` — neither is component-neutral | `feeds_speeds/machines.py` → `MachineProfile` (feeds-scoped) | `UNKNOWN` | both incumbents are partial and scoped | `UNKNOWN` | `UNKNOWN` |
| Tool library | categories, geometry, operating constraints | `NOT_LOCATED` | `data_registry.Registry`; `routers/tooling/post_processor_router.py` | `UNKNOWN` | `feeds_speeds/tools.py` → `Tool` | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Safety validation / policy | mandatory machine-ready gate | `NOT_LOCATED` | `rmos/policies/safety_policy.py`, `rmos/policies/saw_safety_gate.py`, `rmos/fret_cam_guard.py`, `api_v1/rmos_safety.py`, `core/safety.py` (`safety_critical`), `cam/rosette/cnc/cnc_safety_validator.py` | `PRODUCTION_INCUMBENT` | `safety/rules.py` — advisory only | `app/tests/rmos/test_safety_policy.py`, `test_saw_safety_gate.py` | CS has no gate by constitutional choice | Toolbox for policy | `RETAIN_IN_TOOLBOX`; CS scope limited to export preflight |
| Simulation | toolpath simulation, event stream, runtime estimate | `NOT_LOCATED` | `util/gcode/simulator.py` — modal state machine, canned-cycle expansion, G17/18/19 arcs, backplot segments, warnings; consolidated simulation routers | `PRODUCTION_INCUMBENT` (documented fidelity audit) | `preview/toolpath_model.py` — **preview model, not simulation** | `UNKNOWN` | `docs/product-scope.md` places real simulation out of CS scope entirely | Toolbox | `RETAIN_IN_TOOLBOX` |
| LightBurn-oriented output | native LightBurn or interchange file | `NOT_LOCATED` | `UNKNOWN` — not located | `UNKNOWN` | none | `UNKNOWN` | — | `UNKNOWN` | `DESCRIBED_NOT_OBSERVED` |
| Separate / combined output packaging | per-operation and combined files | `NOT_LOCATED` | `cam/runtime_manifest/`, `art_studio/.../inlay_export.py` | `UNKNOWN` — not traced | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Job manifest / checksums / provenance | job identity, source hash, artifact list | `NOT_LOCATED` | `cam/runtime_provenance/`, `cam/runtime_manifest/`, `cam/runtime_admission/` | `UNKNOWN` — not traced | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |
| Deterministic artifact naming | `{job}_{seq}_{op}_{tool}_{units}.{ext}` | `NOT_LOCATED` | `UNKNOWN` | `UNKNOWN` | none | `UNKNOWN` | — | `UNKNOWN` | `UNKNOWN` |

---

## D. Product-experience capabilities

Recorded because the audit found **no incumbent** for these. They are the
strongest candidates for a distinctive Creation Studio role.

| Capability | Toolbox incumbent | CS existing capability | Behavioral tests | Recommended authority | Migration disposition |
| --- | --- | --- | --- | --- | --- |
| Offline / local-first operation | none — Toolbox is a FastAPI service (Docker, Railway) | CS is a local Python package + `camstudio` CLI + static browser app | `python/tests/test_cli_*.py` | **Creation Studio** | genuine CS role |
| G-code education and explanation | not located | `docs/gcode-basics.md`, `docs/quick-start.md`, validator diagnostic explanations | `python/tests/test_validator*.py` | **Creation Studio** | genuine CS role |
| Guided, progressive-disclosure authoring | web client under `packages/client` (service-backed) | `app/` + `src/` browser shell | `tests/*.test.js` | `UNKNOWN` — needs a UX comparison | possible CS role |
| Educational starter dialects (non-certified) | none — Toolbox posts are controller-named and production-shaped | `gcode/dialects.py` | `python/tests/test_generator.py`, `test_golden_parity.py` | **Creation Studio** | genuine CS role |
| Advisory feeds and speeds | `UNKNOWN` | `feeds_speeds/` | `python/tests/test_feeds_speeds.py`, `test_feeds_diagnostics.py` | **Creation Studio** | genuine CS role |

---

## Summary of counts

| Disposition | Rows |
| --- | --- |
| `REUSE` / `REUSE` variants | 11 |
| `EXTRACT_SHARED` (alone or paired) | 4 |
| `RETAIN_IN_TOOLBOX` | 4 |
| `DEPRECATE_DUPLICATE` | 2 |
| `DESCRIBED_NOT_OBSERVED` | 3 |
| `UNKNOWN` | 15 |
| `REIMPLEMENT_WITH_JUSTIFICATION` | **0** |

Fifteen `UNKNOWN` rows is the honest state after one increment. Reducing them is
tracing work, not implementation work — see
[`CAM_CS_01_NEXT_INCREMENT_OPTIONS.md`](CAM_CS_01_NEXT_INCREMENT_OPTIONS.md).
