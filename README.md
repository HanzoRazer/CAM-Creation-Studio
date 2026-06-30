# CAM-Creation-Studio

**A standalone learning and authoring environment for simple CNC, laser, and Marlin-style G-code.**

CAM-Creation-Studio helps you *understand* G-code, *generate* starter programs,
*preview* motion, and *calculate advisory* feeds and speeds. It is built for
beginners and small shops who want to read a file, write their first program,
and see the toolpath before committing to a cut.

> ⚠️ **Educational tool.** The output is a starting point, not certified machine
> output. Preview is **not** simulation. Always verify a program — and air-cut
> above the stock — before running it on real hardware.

---

## What it is

- A **browser-first** app for authoring simple G-code by hand or from an image.
- A place to **learn** the handful of G/M-codes you actually need.
- A **preview** of travel/cut/burn motion in the XY plane.
- An **advisory** feeds-and-speeds helper (in progress) with conservative presets.
- A small, **testable**, modular codebase you can read and extend.

## What it is **not**

- ❌ A certified post-processor or "production-ready" machine output.
- ❌ A guarantee that generated code is *safe to run*.
- ❌ A real collision/material simulator.
- ❌ A machine sender/streamer.
- ❌ A CAM engine, and **not** a module of CAM Assist (see below).

## Current features

- Manual G-code authoring: G0/G1/G2/G3 moves with X/Y/Z/F (+ I/J arcs, E on Marlin).
- Machine families: **Marlin 3D printer**, **generic CNC mill**, **GRBL laser** (starter dialect profiles).
- Header/footer generation: units, positioning, homing, heaters/spindle/beam, safe-Z retract, park, end.
- **Image → etch** workflows: raster fill and vector outline (marching squares), by beam power or Z depth.
- Live XY toolpath **preview** with depth shading and travel vs. cut/burn styling.
- Copy / download `.gcode`.

## Roadmap

This phase converts the original single-file concept into a structured,
browser-first foundation. Planned next:

- Non-blocking **validator** with safety warnings (missing safe Z, cut without feed, spindle off, …).
- Advisory **feeds/speeds** calculator + material/tool/machine presets.
- Extracted **preview** and **image** modules with their own tests.
- Documentation set and a tagged `v0.1.0-browser-alpha` release.

See [docs/product-scope.md](docs/product-scope.md) for the full scope.

## Quick start

```bash
npm install
npm run dev      # serve the app at the printed localhost URL
npm test         # run the test suite (Vitest)
npm run build    # emit a static bundle to dist/
```

The app lives in [app/](app/) and imports shared logic from [src/](src/).
See [docs/quick-start.md](docs/quick-start.md).

## Relationship to CAM Assist

CAM-Creation-Studio is a **standalone** repository. It is **not** a CAM Assist
module and introduces **no** dependency on CAM Assist in this phase.

- **CAM Assist** owns manufacturing intent, review, risk, assumptions, and traceability.
- **CAM-Creation-Studio** owns execution-adjacent authoring, education, feeds/speeds, preview, and G-code learning.

A future, optional one-way relationship may exist
(`CAM Assist → Production Shop Handoff → CAM-Creation-Studio`), but **no
dependency exists today**. See
[docs/future-cam-assist-relationship.md](docs/future-cam-assist-relationship.md).

## Safety

Read [docs/safety-disclaimer.md](docs/safety-disclaimer.md) before using any
generated output. G-code does exactly what it says — including the mistakes.

## License

MIT — see [LICENSE](LICENSE).
