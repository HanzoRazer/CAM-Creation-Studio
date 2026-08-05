# Architecture

## Source-of-truth pivot

CAM-Creation-Studio's core is being built as a **Python package**. The earlier
browser/Vite work is preserved, but it is a prototype — not the main
architecture.

```text
HTML files   = prototypes / behavioral references / archived provenance
Python files = real application core
Future UI    = optional wrapper around the Python core
```

Why Python for the core: feeds/speeds, parsing, validation, preview modeling,
and stronger image/toolpath processing are all easier to build, test, and grow
in Python than in a single-file browser app.

## Layers

| Layer | Location | Status |
|-------|----------|--------|
| Python core (logic) | [`../python/cam_creation_studio`](../python/cam_creation_studio) | **Primary source of truth** |
| Browser prototype (UI + JS logic) | [`../app`](../app), [`../src`](../src) | Prototype / behavioral reference |
| Original DC apps | [`../archive/original-html`](../archive/original-html) | Provenance archive |

The JS work may remain as prototype preservation unless it conflicts with the
Python architecture. New feature work targets the Python core.

## Python core modules

- `shared/` — numbers, units (pure helpers)
- `gcode/` — `formatter`, `dialects`, `generator`, `parser`, `validator`
- `feeds_speeds/` — `calculator` + `materials` / `tools` / `machines` presets (advisory)
- `geometry/` — DXF import → neutral 2D geometry model (`import_dxf` → `GeometryCollection`); geometry only, no machining. Uses the optional `ezdxf` dependency behind the `dxf` extra. See [GEOMETRY_IMPORT.md](GEOMETRY_IMPORT.md)
- `preview/` — `toolpath_model` (neutral travel/cut/burn segments; a model, not a simulation)
- `image/` — `field`, `marching_squares`, `raster_etch`, `outline_etch`
- `safety/` — `rules` (standing reminders + machine-tailored checklist)
- `handoff/` — `handoff` (feeds/speeds → Creator advisory contract)

No GUI is included in this pass; the core is headless and fully unit-tested with
the standard library only.

## Non-negotiables (unchanged by the pivot)

- Educational framing: starter profiles, advisory feeds/speeds, "preview is not
  simulation," nothing "safe to run." See [safety-disclaimer.md](safety-disclaimer.md).
- **No CAM Assist dependency.** See [future-cam-assist-relationship.md](future-cam-assist-relationship.md).
- **No machine-readiness or certification claims.** Export gating is called
  *preflight*. See [architecture/EXPORT_PREFLIGHT_SEMANTICS.md](architecture/EXPORT_PREFLIGHT_SEMANTICS.md).

## Relationship to the Luthiers Toolbox

> ✅ **RATIFIED 2026-08-05** by the Project Owner at merge commit `831680f`
> (PR #8). The boundary and its §7 prohibitions are binding architecture until
> superseded or a re-review trigger fires; they no longer expire.
>
> Ratification approved the investigation record and the guardrails. It did
> **not** authorize shared-package extraction, Toolbox runtime changes, CAM
> migration, or removing an incumbent — each needs its own reviewed increment —
> and it did not resolve the open questions or the fifteen `UNKNOWN` rows in the
> comparison matrix. Review states and the nine re-review triggers are in
> [CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md §9](architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md).
>
> The terminology rule in the previous section stands on separate authority —
> it restates [product-scope.md](product-scope.md) and was already
> constitutional, so it is unaffected either way.

The Toolbox is the incumbent design **and** manufacturing runtime; Creation
Studio does not independently reimplement its CAM algorithms. The ratified
boundary and the prohibited-duplication list are in
[architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md](architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md),
backed by the evidence in [migration/](migration/):

- [CAM_CS_01_REPOSITORY_MAPPING.md](migration/CAM_CS_01_REPOSITORY_MAPPING.md) — real topology; handoff paths mapped or marked nonexistent
- [CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md](migration/CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md) — capability-by-capability incumbent inventory
- [CAM_CS_01_REFERENCE_ARTIFACT_SEARCH.md](migration/CAM_CS_01_REFERENCE_ARTIFACT_SEARCH.md) — `REFERENCE_ARTIFACT_NOT_LOCATED`
- [FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md](migration/FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md) — comparison matrix with explicit unknowns
- [CAM_CS_01_NEXT_INCREMENT_OPTIONS.md](migration/CAM_CS_01_NEXT_INCREMENT_OPTIONS.md) — bounded options for review

Those documents contain **point-in-time inventories** of another repository —
file counts, module paths, test names. They were verified against one commit and
will drift. Each carries an *Evidence freshness* section; re-verify before
relying on a specific count or path.
