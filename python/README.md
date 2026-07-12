# CAM-Creation-Studio — Python Core

This package is the **primary source of truth** for CAM-Creation-Studio's logic.
The browser/JS app under [`../app`](../app) and [`../src`](../src) is preserved
as a behavioral reference and prototype; this Python core is where the real
application is built.

> ⚠️ **Educational.** Nothing here is a certified post-processor and no output is
> guaranteed safe to run. Always verify a program — and air-cut — before running.

## Layout

```text
cam_creation_studio/
  shared/        numbers, units
  gcode/         formatter, dialects, generator, parser, validator
  feeds_speeds/  calculator, materials, tools, machines (advisory)
  geometry/      DXF import -> neutral 2D geometry model (optional: ezdxf)
  preview/       toolpath_model (neutral travel/cut/burn segments)
  image/         field, marching_squares, raster_etch, outline_etch
  safety/        rules (standing safety reminders + checklist)
  handoff/       handoff (feeds/speeds -> Creator advisory contract)
tests/           pytest suite mirroring each module
```

No GUI in this pass — this is the headless core. A UI (CLI, web, or desktop)
becomes an optional wrapper around it later.

## Develop

```bash
cd python
python -m pytest          # run the suite (no third-party deps required)
pip install -e .[dev]     # optional: editable install
```

## Quick taste

```python
from cam_creation_studio.gcode.generator import build_program
from cam_creation_studio.gcode.validator import validate_program
from cam_creation_studio.feeds_speeds.calculator import calculate_feeds

cfg = {"machine": "genericCnc", "units": "mm", "positioning": "abs",
       "home": True, "spindleOn": True, "spindleRpm": 12000, "safeZ": 5}
job = {"mode": "manual", "moves": [
    {"type": "G0", "x": "0", "y": "0"},
    {"type": "G1", "z": "-0.5", "f": "300"},
    {"type": "G1", "x": "40", "f": "800"},
]}

program = build_program(cfg, job)
warnings = validate_program(program, machine="genericCnc")  # advisory only
feeds = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, material="mdf")
```

## DXF import (optional `dxf` extra)

Import 2D DXF geometry into a neutral, machine-independent model — *what geometry
exists*, never how it will be machined. This is the one place a third-party
dependency is used, and it stays **optional**: the core still installs with zero
required runtime deps.

```bash
pip install -e .[dxf]      # pulls in ezdxf (>=1.4,<2)
```

```python
from cam_creation_studio.geometry import import_dxf, summarize

collection = import_dxf("part.dxf")   # -> GeometryCollection (coords in mm)
print(summarize(collection))          # counts, bounds, layers
for d in collection.diagnostics:      # advisory: nothing discarded silently
    print(d.severity.value, d.code, d.message)

text = collection.to_json()                        # serialize (source order kept)
restored = collection.__class__.from_json(text)    # kind-dispatched round-trip
```

Calling `import_dxf` without `ezdxf` installed raises `EzdxfNotInstalled` with an
install hint. See [../docs/GEOMETRY_IMPORT.md](../docs/GEOMETRY_IMPORT.md) for the
full architecture and public API.

## Design rules

- **DOM-free, dependency-free core.** Standard library only for the core; the DXF
  importer is the sole optional dependency (`ezdxf`, behind the `dxf` extra) and
  is never required to import or test the package. Image input is a neutral
  `DarknessField`, not a specific image library.
- **Advisory, not authoritative.** Feeds/speeds and dialects are starting points;
  the validator warns but never blocks.
- **No CAM Assist dependency.** See [../docs/future-cam-assist-relationship.md](../docs/future-cam-assist-relationship.md).
