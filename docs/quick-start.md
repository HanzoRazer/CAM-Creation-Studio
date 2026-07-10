# Quick Start

CAM-Creation-Studio is browser-first. You need [Node.js](https://nodejs.org)
(v18+; developed on v24) and npm.

## Run the app

```bash
npm install      # one-time: install Vite + Vitest
npm run dev      # serve the app; open the printed http://localhost URL
```

`npm run dev` serves [app/index.html](../app/index.html). The app imports shared
logic from [src/](../src/), so use the dev server rather than opening the HTML
via `file://`.

## Run the tests

```bash
npm test         # run once
npm run test:watch
```

## Build a static bundle

```bash
npm run build    # emits dist/
npm run preview  # serve the built bundle
```

## Using the app

1. **Pick a machine** in the top bar: *Marlin · 3D Printer* or *CNC Mill*.
2. **Set the header**: units (mm/in), positioning (abs/rel), home on/off, safe Z.
   Marlin shows hotend/bed temps; CNC shows the spindle toggle and RPM.
3. **Choose a builder mode**:
   - **Manual moves** — add G0/G1/G2/G3 moves with X/Y/Z/F (and I/J for arcs,
     E on Marlin). Reorder or delete rows.
   - **Etch from image** — upload a PNG/JPG, set the work area, pick *raster
     fill* or *vector outline*, and cut by *beam power* or *Z depth*.
4. **Watch the preview** (top-view XY): dashed = travel, solid = cut/burn, with
   depth shading on cut moves.
5. **Copy** or **Download .gcode** from the top bar.

> Remember: the preview is not a simulation, and the output is a starting point.
> See [safety-disclaimer.md](safety-disclaimer.md).

## Command-line interface (Python core)

Prefer the terminal or scripting? The Python core ships a `camstudio` CLI that
generates, parses, validates, and inspects G-code, and computes advisory
feeds/speeds. It calls the same core the app does — no separate logic.

```bash
cd python
pip install -e .          # provides the `camstudio` command
camstudio --help

# Generate G-code from a {config, job} JSON job, then inspect it.
camstudio generate ../examples/cnc-pocket-demo.json -o square.gcode
camstudio validate square.gcode --machine genericCnc     # advisory
camstudio parse square.gcode --json
camstudio preview square.gcode

# Advisory feeds & speeds (a starting point — verify before cutting).
camstudio feeds -d 6 -n 2 -r 18000 --material aluminum --woc 1.5 --doc 6
```

Add `--json` to any command for machine-readable output. Exit codes: `0` success,
`1` validation failure, `2` bad arguments, `3` file error. Full command reference
in [python/README.md](../python/README.md#command-line-interface).

## Learn the language

New to G-code? Start with [gcode-basics.md](gcode-basics.md).
