# Validation Rules

Validation is **advisory** and **non-blocking**. `validate_program(text, machine)`
parses a program into a shared context, runs four rule modules over it, and
returns a flat list of `Diagnostic` objects. Nothing here is a safety guarantee —
the diagnostics are hints that help a beginner catch common mistakes.

```
text ──► build_context ──► structure ──► dialect ──► crossdialect ──► safety ──► [Diagnostic, ...]
```

Every `Diagnostic` carries a `severity` (`info` / `warning` / `danger`), a stable
string `code`, a human `message`, and an optional 1-based `line`.

## Modules

| Module | Concern | Emits |
|---|---|---|
| `structure.py` | Is the program well-formed as a whole? | `UNITS_NOT_DECLARED`, `DUPLICATE_UNITS`, `EMPTY_PROGRAM_BODY`, `MISSING_SAFE_Z`, `NO_FOOTER_SHUTDOWN`, `UNKNOWN_GCODE` |
| `dialect.py` | Does it fit the named machine's dialect? | `UNSUPPORTED_DIALECT`, `ARC_ON_NON_ARC_DIALECT` |
| `crossdialect.py` | Is a command in the wrong machine family? | `EXTRUDER_WORD_IN_CNC`, `HEATER_COMMAND_IN_CNC`, `SPINDLE_COMMAND_IN_FDM`, `MARLIN_COMMAND_IN_GRBL` |
| `safety.py` | Could it do something dangerous? | `CUT_WITHOUT_FEED`, `ARC_WITHOUT_CENTER_OR_RADIUS`, `EXTRUSION_WITHOUT_HOTEND`, `NEGATIVE_Z_IN_LASER_MODE`, `SPINDLE_OFF_WITH_CUTS` |

The dialect rules stay silent when no machine is named; the generic
structure/safety rules always apply.

## Canonical codes

`validator/codes.py` is the single source of truth for the code vocabulary. The
eleven **canonical** codes CS-003 promises, in spec order:

| Code | Severity | Meaning |
|---|---|---|
| `EMPTY_PROGRAM` | warning | No motion moves at all. (emitted as `EMPTY_PROGRAM_BODY`; see aliases) |
| `UNITS_NOT_DECLARED` | danger | No `G20`/`G21` — mm vs inch is ambiguous. |
| `CUT_WITHOUT_FEED` | warning | A cutting move with no feed rate in effect. |
| `ARC_WITHOUT_CENTER_OR_RADIUS` | warning | `G2`/`G3` lacking `I/J` center or `R` radius. |
| `EXTRUDER_WORD_IN_CNC` | warning | An `E` word on a CNC/router program. |
| `HEATER_COMMAND_IN_CNC` | warning | `M104/M109/M140/M190` on a CNC/router program. |
| `SPINDLE_COMMAND_IN_FDM` | warning | `M3/M4` on an FDM printer program. |
| `MARLIN_COMMAND_IN_GRBL` | warning | A Marlin-only command (heater or `E`) on a GRBL/laser dialect. |
| `NO_FOOTER_SHUTDOWN` | info | No program end (`M2`/`M30`). |
| `MISSING_SAFE_Z` | warning | No rapid to a safe Z retract. |
| `UNKNOWN_GCODE` | warning | A `G` word outside the recognized vocabulary. |

The validator also emits finer-grained codes (`DUPLICATE_UNITS`,
`ARC_ON_NON_ARC_DIALECT`, `EXTRUSION_WITHOUT_HOTEND`, `NEGATIVE_Z_IN_LASER_MODE`,
`SPINDLE_OFF_WITH_CUTS`, `UNSUPPORTED_DIALECT`).

## Legacy aliases

Some rules keep an older emitted code for back-compat. `codes.LEGACY_ALIASES`
maps each to its canonical spec name (currently `EMPTY_PROGRAM_BODY → EMPTY_PROGRAM`).
Check for a code with the alias-aware helper rather than raw string equality:

```python
from cam_creation_studio.gcode.validator import validate_program, has_code

diags = validate_program(program_text, "genericCnc")
if has_code(diags, "EMPTY_PROGRAM"):     # resolves EMPTY_PROGRAM_BODY too
    ...
```

## Machine families

The context classifies a program by family so the cross-dialect rules know what
counts as "wrong":

- **CNC-like** — `machine` is `cnc`/`genericCnc`, or unnamed with no printer/laser
  signals. Spindle drives the cut; `E` and heater words are foreign.
- **Printer (FDM)** — an `E` word or a heater command (`M104/M109/M140/M190`) is
  present. Spindle commands are foreign.
- **Laser / GRBL** — `machine` is `laser`/`laserGrbl`. Negative Z and Marlin-only
  commands are foreign.

## What validation is not

It never rewrites or blocks a program, and it is not a certified safety check.
Always verify a program before running it on real hardware.
