# CAM Creation Studio — Provisional Product Boundary

**Status:** Provisional. Subject to the migration study. Not a final architecture.
**Supersedes:** the design-versus-manufacturing split asserted in CAM-CS-01 §3.
**Evidence:** [`CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md`](../migration/CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md)
**Last verified:** 2026-08-04 · CS `0442feb0` · Toolbox `ffd155e4`
**Review status:** **NOT SIGNED OFF.** Awaiting architectural review of Increment 1.

> ⚠️ This document introduces concrete prohibitions (§7) on the strength of a
> single investigation. That is deliberate — the prohibitions exist to stop
> duplication *while* the boundary is being decided, not to settle it. If this
> document is still governing work months from now without a sign-off, that is a
> process failure, not a ratification. §9 records what would firm it up.

---

## 1. Why the original boundary was withdrawn

CAM-CS-01 §3 asserted a clean split: the Luthiers Toolbox owns design and
engineering; CNC Creation Studio owns "machining authoring, operation planning,
toolpath generation, simulation, post-processing, and manufacturing-oriented
user workflows."

Repository evidence does not support the second half. Every responsibility in
that list has a Toolbox incumbent, most of them test-backed:

| Asserted CS responsibility | Toolbox incumbent |
| --- | --- |
| Toolpath generation | `app/cam/` — 320 Python files, ~2.9 MB, 23 subpackages |
| Operation planning | `app/cam/neck/orchestrator.py` (`NeckPipeline`) |
| Simulation | `app/util/gcode/simulator.py` (25 KB, documented fidelity audit) |
| Post-processing | `app/cam/post_processor.py`; 8 controllers declared in `app/schemas/cam_fret_slots.py` |
| Manufacturing safety | `app/rmos/policies/`, `app/cam/rosette/cnc/cnc_safety_validator.py` |
| Fret-slot CAM specifically | `app/calculators/fret_slots_cam.py`, `fret_slots_export.py`, `fret_slots_fan_cam.py`, `app/cam/neck/fret_slots.py` |

The original boundary described a **desired future state as present fact**. Acting
on it would have produced a second CAM spine rather than a product boundary.

---

## 2. Provisional relationship

```text
Luthiers Toolbox
    Incumbent design and manufacturing runtime
    Existing CAM algorithms and authorities
                  |
                  | reviewed contracts or extracted packages
                  v
CNC Creation Studio
    Focused manufacturing-authoring experience
    Guided workflow, local composition, preview,
    educational interaction, and artifact assembly
```

This is a **provisional** boundary. It is explicitly **not** permission to couple
the two applications directly to each other's internal modules. Creation Studio
must not import from `services/api/app/**`, and the Toolbox must not import from
`python/cam_creation_studio/**`. Any sharing happens through a reviewed contract
or an extracted, repository-neutral package.

---

## 3. Existing authority

Where authority demonstrably sits today, per the audit.

### Luthiers Toolbox holds

Fret position mathematics (`AUTHORITATIVE`, golden-test-backed) · multiscale and
fan-fret geometry · fretboard outline, taper, and width · the canonical
fretboard document (`fretboard_ecosphere.py`, self-declared single source of
truth) · fret-slot CAM and fan-fret CAM · fret-slot G-code export · controller
post-processors for eight named controllers · post/machine compatibility
reporting · G-code simulation · SVG and inlay intake · CAM guards and RMOS
safety policy · runtime admission, provenance, and manifests · neck pipeline
operation sequencing.

### CAM Creation Studio holds

G-code generation from explicit moves · G-code parsing · advisory validation
with a centralized diagnostic-code registry · educational starter dialects
(`marlin`, `genericCnc`, `laserGrbl`) · a neutral preview model · DXF geometry
import · advisory feeds and speeds with machine/material/tool presets · image
etch (raster fill, vector outline) · the `camstudio` CLI · offline, local-first
operation · a standing safety-messaging vocabulary.

### Neither holds

Holding-tab generation and male-plug/pocket compensation were not located in
either repository. They are the clearest genuine-gap candidates.

---

## 4. Desired product experience for Creation Studio

The capabilities with **no Toolbox incumbent** are where a distinctive role
exists. From the audit's §D:

1. **Offline, local-first operation.** The Toolbox is a FastAPI service with
   Docker and Railway deployment. Creation Studio is a package, a CLI, and a
   static browser app that runs with no server. This is a real difference in
   kind, not a duplication.
2. **Education and explanation.** Creation Studio's constitutional purpose is to
   make machining knowledge understandable — what a program does, why a warning
   fired, what feed to start from. No Toolbox equivalent was located.
3. **Non-certified starter dialects.** Creation Studio deliberately ships three
   generic dialects rather than controller-named posts. That is a product
   position, not a gap to be filled.
4. **Guided authoring and progressive disclosure.** The user-workflow quality the
   original handoff admired in the standalone application. Comparison against
   `packages/client` is still `UNKNOWN`.
5. **Artifact assembly and job composition** — composing an operator-facing
   package from canonical outputs, without owning the algorithms that produce
   them.

None of these require Creation Studio to own fret mathematics, toolpath
strategies, post-processors, simulation, or safety policy.

---

## 5. Possible shared-package extraction

Where a capability is needed by both products, the resolution is extraction to a
repository-neutral Python package consumed by both — **not** independent
reimplementation. Authority moves to the shared package; it does not fork.

Ranked by evidence, the current extraction candidates are:

| Rank | Capability | Why | Blocker |
| --- | --- | --- | --- |
| 1 | Post/machine compatibility preflight (`cam/postprocessor_boundary.py`) | Its declared posture — *"a report, not machine code"*, GREEN/YELLOW/RED — already matches Creation Studio's constitution. Nothing about it asserts machine readiness. | Stability of CAM Dev Order 6C is `UNKNOWN` |
| 2 | Fret position mathematics (`instrument_geometry/neck/fret_math.py`) | Narrow, pure, deterministic, golden-test-backed. The cleanest possible extraction seam. | Three call sites duplicate it; consolidation is a Toolbox task |
| 3 | Fretboard geometry (`instrument_geometry/body/fretboard_geometry.py`) | Small, pure, depends only on fret math. | Depends on `neck_profiles.FretboardSpec` |
| 4 | SVG intake (`art_studio/.../inlay_geometry_svg.py`, `inlay_import.py`) | Creation Studio has DXF only; SVG is a real gap. | Large surface, tangled with inlay pattern generation |

A shared package must not carry FastAPI, Pydantic-only contracts, or RMOS
context if Creation Studio is to consume it — Creation Studio is dataclass-only
by convention (Ruling 6). Reconciling that is part of any extraction proposal.

---

## 6. Possible future migration

Creation Studio could become the final manufacturing authority only through an
explicit, staged program in which Toolbox incumbents are inventoried, replacement
contracts are approved, parity is demonstrated, consumers are migrated, old
authorities are deprecated, and duplicates are removed.

That is a cross-repository migration program with its own governance. It is not
a fretboard feature order, and no part of it is authorized by CAM-CS-01.

---

## 7. Prohibited parallel implementation

Until the migration study concludes, Creation Studio **must not** independently
implement:

- fret position mathematics or fret-placement methods;
- multiscale / fan-fret geometry;
- fretboard outline, taper, or radius geometry;
- fret-slot toolpath strategies;
- controller-named post-processors (GRBL, Mach3, Mach4, LinuxCNC, Fanuc, Haas,
  PathPilot, MASSO);
- G-code simulation;
- manufacturing safety policy;
- SVG intake, where the Toolbox implementation would serve.

Building any of these requires a `REIMPLEMENT_WITH_JUSTIFICATION` disposition,
which requires explicit approval plus documented evidence that reuse, extraction,
and adaptation are all unsuitable. That disposition is assigned nowhere in the
current matrix.

### What this prohibition does not cover

The list above is narrow on purpose. It prohibits **standing a second
implementation of a Toolbox algorithm inside Creation Studio**. It does not
prohibit ordinary product work. Explicitly still allowed:

- **Creation Studio's existing capabilities.** `gcode/`, `preview/`,
  `feeds_speeds/`, `geometry/` (DXF), `image/`, `safety/`, and `cli/` continue
  to be developed under the existing scope. None of them needs a boundary
  exception.
- **Local abstractions over Creation Studio's own data** — helpers, view models,
  formatting, caching, CLI ergonomics. Operating on CS data is not
  reimplementing a Toolbox algorithm.
- **Throwaway prototypes and spikes** that are not merged to `main`. Learning
  what an integration would cost is how the boundary gets decided; the
  prohibition applies to durable authority, not to experiments.
- **Adapters and wrappers** that call canonical code rather than restating it.
- **Artifact assembly** — packaging, naming, and presenting outputs Creation
  Studio did not compute.

### Telling the three apart

| | Definition | Test |
| --- | --- | --- |
| **Implementation** | Creation Studio computes the answer itself | Delete the Toolbox — does CS still produce a result? If yes, it is an implementation. |
| **Adapter** | Creation Studio asks something else and translates the answer | Delete the Toolbox — does CS fail cleanly with "no source"? Then it is an adapter. |
| **Artifact assembly** | Creation Studio arranges outputs it did not compute | Does CS touch any dimension, coordinate, feed, or depth? If no, it is assembly. |

Only the first is prohibited. When a case is genuinely ambiguous, treat it as an
open question for review rather than assuming either answer.

---

## 8. Terminology

Creation Studio's safety vocabulary is governed by
[`EXPORT_PREFLIGHT_SEMANTICS.md`](EXPORT_PREFLIGHT_SEMANTICS.md) and
`docs/product-scope.md`. Nothing in this boundary permits Creation Studio to
assert machine readiness, certification, or that output is safe to run —
regardless of which repository produced the underlying toolpath.

---

## 9. Review status

Provisional pending architectural review of Increment 1. The open questions that
would firm it up are listed in
[`CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md`](../migration/CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md) §7,
and the bounded next steps in
[`CAM_CS_01_NEXT_INCREMENT_OPTIONS.md`](../migration/CAM_CS_01_NEXT_INCREMENT_OPTIONS.md).
