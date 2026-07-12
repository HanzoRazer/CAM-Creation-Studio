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

## Command-line interface

The `camstudio` CLI exposes the core as a scriptable app. It is a thin
presentation layer — argument parsing, formatting, and exit codes only — and
never duplicates business logic.

```bash
cd python
pip install -e .          # provides the `camstudio` command
camstudio --help
```

Commands (every command takes `--json` for machine-readable output; human text
is the default):

```bash
# Generate G-code from a {config, job} JSON job (file or stdin).
camstudio generate ../examples/cnc-pocket-demo.json -o out.gcode
camstudio generate ../examples/cnc-pocket-demo.json --machine marlin   # override config
cat job.json | camstudio generate -
# Note: adding --json writes a JSON envelope ({"gcode": "..."}), not raw
# G-code — don't combine it with -o unless you want the JSON on disk.

# Validate (advisory). Default exit 1 if any warning/danger diagnostic is present;
# relax with --fail-on danger (ignore warnings) or --fail-on never (always exit 0).
camstudio validate out.gcode --machine genericCnc
camstudio validate out.gcode --fail-on danger
camstudio validate out.gcode --json

# Parse: move counts, inferred header, bounds, travel distance.
camstudio parse out.gcode --json

# Preview: toolpath summary (counts + distances per motion type; no rendering).
camstudio preview out.gcode

# Feeds & speeds (ADVISORY — verify before cutting).
camstudio feeds -d 6 -n 2 -r 18000 --material aluminum --woc 1.5 --doc 6
camstudio feeds -d 6 -n 2 -r 18000 --chipload 0.05 --json

camstudio version
```

Exit codes: `0` success · `1` validation failure · `2` bad arguments/input ·
`3` file error · `70` internal error (an unexpected bug — please report it).

## Design rules

- **DOM-free, dependency-free core.** Standard library only; image input is a
  neutral `DarknessField`, not a specific image library.
- **Advisory, not authoritative.** Feeds/speeds and dialects are starting points;
  the validator warns but never blocks.
- **No CAM Assist dependency.** See [../docs/future-cam-assist-relationship.md](../docs/future-cam-assist-relationship.md).
