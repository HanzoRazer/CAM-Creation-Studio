# CAM-CS-01 — Repository Mapping

**Status:** Increment 1 deliverable (documentation and evidence only)
**Evidence commit (CAM-Creation-Studio):** `0442feb06e62944a58195af2a23a0151e37b05d9`
**Evidence commit (luthiers-toolbox):** `ffd155e436be89c15cdb0b83a96dc7d2cbefa251`
**Test baseline at time of survey:** `python -m pytest python/tests -q` → **310 passed**

This document records the real topology of CAM-Creation-Studio and maps every
illustrative path from the original CAM-CS-01 handoff onto an actual path or
marks it nonexistent. It changes no production behavior.

---

## 1. Package roots

| Root | Language | Role |
| --- | --- | --- |
| `python/cam_creation_studio/` | Python | **The application core.** Canonical source of truth for generation, parsing, validation, feeds/speeds, preview, geometry import, image etch, CLI. |
| `python/tests/` | Python | 30 test modules, 310 tests. |
| `app/` | HTML/JS/CSS | Browser UI shell — `index.html`, `main.js`, `styles.css`. |
| `src/` | JS | Browser-side modules: `gcode/{dialects,formatter,generator}.js`, `handoff/handoff.js`, `shared/{numbers,units}.js`. |
| `tests/` | JS | `gcode-generator.test.js`, `handoff.test.js`. |
| `dist/` | build output | Vite bundle. |
| `archive/original-html/` | HTML | Provenance archive of the original single-file tools (G-code Creator, Feeds & Speeds Calculator, Preview Dashboard, Quick-Start Manual). **No fretboard artifact present.** |
| `examples/`, `docs/`, `schemas/` | — | `schemas/` does **not** exist. |

The package docstring in `python/cam_creation_studio/__init__.py` states the
position explicitly:

> The browser/JS prototype under `app/` and `src/` is preserved as a behavioral
> reference and provenance archive; this Python package is the real application
> core.

### Ruling 6 confirmation

The handoff's proposed root `app/cam_creation_studio/` **must not be created**.
`app/` is the browser UI. The Python package root is `python/cam_creation_studio/`.

---

## 2. Actual Python module inventory

```
python/cam_creation_studio/
  __init__.py            public API re-exports (enums + domain model)
  enums.py               Units, MoveType, CutMode, MachineType, DiagnosticSeverity
  models.py              Move, ArcMove, Diagnostic, ProgramHeader/Footer,
                         GCodeProgram, move_from_dict; re-exports
                         MachineProfile / Material / Tool / FeedRecommendation

  cli/                   main, dispatch, common, errors, output
    commands/            feeds, generate, parse, preview, validate, version

  feeds_speeds/          calculator (FeedRecommendation), machines
                         (MachineProfile), materials (Material), tools (Tool)

  gcode/                 body, dialects, footer, formatter, generator, header,
                         parser, words
    validator/           codes, crossdialect, dialect, safety, structure,
                         _context

  geometry/              bounds, diagnostics, entities, importer, layers,
                         models, summary          (DXF intake — CS-008)

  handoff/               handoff
  image/                 field, marching_squares, outline_etch, raster_etch
  preview/               toolpath_model
  safety/                rules
  shared/                geometry, ids, numbers, serialization, units
```

---

## 3. Existing authorities inside CAM-Creation-Studio

| Responsibility | Canonical location | Notes |
| --- | --- | --- |
| Domain vocabulary | `models.py` | Frozen dataclasses, `slots=True`. |
| Closed enumerations | `enums.py` | All `str`-based for wire compatibility. |
| Dialect registry | `gcode/dialects.py` | `Dialect` dataclass, `_REGISTRY`, `_ALIASES`, `get_dialect()`, `list_dialects()`. Three entries: `marlin`, `genericCnc`, `laserGrbl`. |
| G-code emission | `gcode/generator.py` + `header/body/footer/formatter/words` | |
| G-code parsing | `gcode/parser.py` | |
| Validation | `gcode/validator/` | `codes.py` owns diagnostic codes; `structure`, `dialect`, `crossdialect`, `safety` are the rule families. Advisory — never blocks. |
| Diagnostics | `models.Diagnostic` (`severity`, `code`, `message`, `line`) | Plus `geometry/diagnostics.py` for import findings. |
| Preview model | `preview/toolpath_model.py` (436 lines) | Neutral model consumed by preview. |
| Geometry import | `geometry/` | DXF only, `ezdxf` optional (CS-008). |
| Geometry primitives | `shared/geometry.py` | `Point`, `Bounds`, `bounds()`. |
| Machine profiles | `feeds_speeds/machines.py` → `MachineProfile` | Feeds-oriented, not post-oriented. |
| Tools / materials | `feeds_speeds/tools.py`, `materials.py` | |
| Units | `shared/units.py` | |
| Serialization | `shared/serialization.py` | `to_dict` / `from_dict` for dataclasses. |
| IDs | `shared/ids.py` | |
| Safety messaging | `safety/rules.py` | **Advisory strings only.** `DISCLAIMER` + 8 `SafetyRule` entries + `checklist()`. There is no gate. |
| CLI | `cli/` | `camstudio` entry point (CS-007). |

### Conventions carried forward from CS-002 … CS-008

- Frozen dataclasses with `slots=True`; no Pydantic anywhere in the package.
- `str`-based enums so members compare equal to and serialize as their wire string.
- Hybrid dataclass/dict API with `to_dict` / `from_dict` / `move_from_dict`.
- Diagnostic codes centralized in `gcode/validator/codes.py`, with aliases kept green.
- Optional third-party dependencies degrade gracefully (`ezdxf` in `geometry/`).
- No `Decimal` in the codebase today; floats throughout.

---

## 4. Handoff path → actual path

| Handoff illustrative path | Actual path | Status |
| --- | --- | --- |
| `app/cam_creation_studio/` | `python/cam_creation_studio/` | **REMAPPED** — `app/` is the browser UI |
| `contracts/design_intent.py` | — | **NONEXISTENT** |
| `contracts/manufacturing_request.py` | — | **NONEXISTENT** |
| `contracts/toolpath.py` | nearest incumbents: `models.GCodeProgram`, `preview/toolpath_model.py` | **PARTIAL INCUMBENT** |
| `contracts/artifacts.py` | — | **NONEXISTENT** |
| `contracts/diagnostics.py` | `models.Diagnostic` + `gcode/validator/codes.py` + `geometry/diagnostics.py` | **INCUMBENT EXISTS** |
| `workflows/registry.py`, `workflows/base.py` | — | **NONEXISTENT** |
| `workflows/fretboard/**` | — | **NONEXISTENT** (no fretboard code of any kind in CS) |
| `machines/models.py`, `machines/registry.py` | `feeds_speeds/machines.py` | **INCUMBENT EXISTS** (feeds-scoped) |
| `machines/profiles/*.json` | — | **NONEXISTENT** (no JSON profile loading) |
| `tooling/models.py`, `library.py`, `validation.py` | `feeds_speeds/tools.py` | **INCUMBENT EXISTS** (partial) |
| `stock/models.py`, `stock/geometry.py` | — | **NONEXISTENT** |
| `geometry/primitives.py` | `shared/geometry.py` | **INCUMBENT EXISTS** |
| `geometry/bounds.py` | `geometry/bounds.py` | **EXISTS** |
| `geometry/transforms.py`, `offsets.py`, `interpolation.py` | — | **NONEXISTENT** |
| `geometry/svg_import.py` | — | **NONEXISTENT** (CS imports DXF only) |
| `toolpaths/primitives.py`, `program.py`, `optimization.py`, `validation.py` | `models.py` + `preview/toolpath_model.py` | **PARTIAL INCUMBENT** |
| `posts/base.py`, `registry.py`, `grbl.py`, `marlin.py`, `linuxcnc.py`, `mach3.py`, `mach4.py`, `lightburn.py` | `gcode/dialects.py` (3 dialects, no named controller posts) | **INCUMBENT EXISTS — different shape** |
| `simulation/**` | `preview/toolpath_model.py` | **PARTIAL** — CS has a preview model; product scope forbids calling it simulation |
| `safety/validate.py`, `models.py`, `policies.py` | `safety/rules.py` | **INCUMBENT EXISTS — advisory only, no gate** |
| `artifacts/naming.py`, `manifest.py`, `packaging.py`, `checksums.py` | — | **NONEXISTENT** |
| `application/generate.py`, `preview.py`, `export.py` | `cli/commands/{generate,preview}.py` | **PARTIAL** — CLI-shaped, not an application layer |
| `cli/fretboard.py`, `parity.py`, `validate_job.py` | `cli/commands/` | **NONEXISTENT** commands; the CLI package itself exists |
| `schemas/*.schema.json` | — | **NONEXISTENT** — no `schemas/` directory |
| `config/machines/`, `config/tools/`, `config/safety/` | — | **NONEXISTENT** |
| `docs/architecture/*` | `docs/architecture/` exists | **EXISTS** — currently `DIALECT_SYSTEM`, `DOMAIN_MODEL`, `FEEDS_SPEEDS_MODEL`, `GCODE_PIPELINE`, `VALIDATION_RULES` |
| `docs/migration/*` | created by this increment | **NEW** |
| `tests/**` | `python/tests/` (flat, not nested by subject) | **REMAPPED** |

### Singular/plural collision check (Decision 10)

No `generator/`+`generators/`, `profile/`+`profiles/`, `post/`+`postprocessors/`,
or `validation/`+`validators/` pairs exist or would be created by this increment.
Note that the handoff's proposed `posts/` package would sit beside the incumbent
`gcode/dialects.py`, which already owns controller-shaped behavior — a
responsibility collision even though the directory names do not collide.

---

## 5. Governing scope documents already in the repository

| Document | Force |
| --- | --- |
| `docs/product-scope.md` | Self-declared constitutional: *"When in doubt about whether something belongs in this project, this document decides."* |
| `docs/safety-disclaimer.md` | Safety posture. |
| `python/cam_creation_studio/safety/rules.py` | `DISCLAIMER` constant shipped with the code. |

`docs/product-scope.md` lists as **out of scope**: certified post-processors and
"production-ready" machine output; machine execution; real collision or
material-removal simulation; automatic machining approval. It mandates the
vocabulary *machine output profiles*, *starter dialect profiles*, *educational
G-code templates*, and forbids *production-ready post processor*,
*machine-certified output*, and *safe to run*.

See [`EXPORT_PREFLIGHT_SEMANTICS.md`](../architecture/EXPORT_PREFLIGHT_SEMANTICS.md)
for how CAM-CS-01's terminology was reconciled with this.

---

## 6. What CAM-Creation-Studio does not have

Recorded so later increments do not rediscover it:

- No fretboard, fret, neck, or instrument-specific code of any kind.
- No SVG intake (DXF only).
- No toolpath *strategy* layer — the package emits programs from explicit moves.
- No operation planner, no operation dependency model, no stock model.
- No artifact manifest, checksum, or packaging.
- No workflow registry.
- No JSON-file-backed machine or tool profiles.
- No blocking validation gate of any kind.
- No `Decimal` usage and no schema files.
