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
