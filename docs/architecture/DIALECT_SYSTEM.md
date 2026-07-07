# Dialect System

Machine independence is a constitutional requirement of the core: the generator,
formatter, parser, and domain model never mention GRBL, Mach4, LinuxCNC, or
Marlin. **Only dialect adapters know those differences.** This document explains
why that boundary exists and how to add a new dialect.

## Why dialects exist

Every machine family opens and closes a program differently:

- a **CNC mill/router** starts its spindle (`M3 S…`) and stops it (`M5`),
- a **laser** keeps the beam off until a cut and toggles power via `S`,
- a **Marlin 3D printer** heats a bed and hotend, waits for temperature, and
  extrudes on the `E` axis.

If that knowledge leaked into the generator, the core would grow a tangle of
`if machine == "marlin"` branches. Instead, the generator asks a `Dialect` object
for its startup and shutdown lines and stays otherwise machine-agnostic. The
header/body/footer builders only ever call:

```python
dialect.header_extras(cfg)   # lines injected after positioning, before safe-Z
dialect.footer_extras(cfg)   # lines injected before park/end
```

## The `Dialect` object

Defined in `gcode/dialects.py`. Each dialect is a frozen dataclass describing how
a machine family behaves — never a certified post-processor:

| Field | Meaning |
|---|---|
| `id` | canonical identifier (`"genericCnc"`, `"laserGrbl"`, `"marlin"`) |
| `label` | human-readable name |
| `allowed_axes` | the axis letters this dialect expects |
| `default_units` | `"mm"` or `"in"` |
| `supports_arcs` | whether G2/G3 are meaningful (drives the `ARC_ON_NON_ARC_DIALECT` check) |
| `startup_comment` | short description of the opening sequence |
| `header_extras(cfg)` | callable → `[LineSpec, ...]` injected into the header |
| `footer_extras(cfg)` | callable → `[LineSpec, ...]` injected into the footer |

The extras callables return `LineSpec(cmd, words, comment)` descriptors, which the
header/footer builders convert into `Line` objects and render — so dialect output
goes through the same single formatter as everything else.

## Registry and aliases

```python
from cam_creation_studio.gcode.dialects import get_dialect, list_dialects

get_dialect("genericCnc")   # canonical
get_dialect("cnc")          # alias → genericCnc
get_dialect("laser")        # alias → laserGrbl
get_dialect("nope")         # raises ValueError
```

The bundled dialects are `marlin`, `genericCnc`, and `laserGrbl`. Aliases
(`cnc`, `laser`) map friendly names onto canonical ids.

## How the validator uses dialects

`gcode/validator/dialect.py` resolves the named machine and emits:

- `UNSUPPORTED_DIALECT` when the machine id is unrecognized, and
- `ARC_ON_NON_ARC_DIALECT` when a program uses G2/G3 on a dialect whose
  `supports_arcs` is `False` (e.g. Marlin).

When no machine is named, dialect checks stay silent — the generic structure and
safety rules still apply.

## Adding a new dialect

1. **Write the extras.** Add `_yourmachine_header(cfg)` and
   `_yourmachine_footer(cfg)` functions in `gcode/dialects.py` returning
   `LineSpec` lists. Read only the config keys you are confident about.
2. **Declare the `Dialect`.** Instantiate it with a unique `id`, the
   `allowed_axes`, `default_units`, `supports_arcs`, and the two callables.
3. **Register it.** Add the instance to the tuple that builds `_REGISTRY`, and
   add any friendly `_ALIASES` entries.
4. **Map header/footer config, if needed.** If your dialect reads new startup
   values, add typed fields to `ProgramHeader` / `ProgramFooter` and surface them
   through `header.py`/`footer.py`'s `_dialect_config(...)` mapping. Keep the
   generator itself unaware of the specifics.
5. **Test it.** Assert the header/footer contain the expected lines and that a
   round-trip still holds. Follow the patterns in
   `tests/test_generator.py` and `tests/test_generator_model.py`.

### Design rules for a dialect

- **Claim only what you are confident about.** These are starter profiles for
  learning and rough bounds-checking, not machine definitions. If you cannot
  assert a controller's post behavior, leave it out (see the BCAMCNC placeholder
  in `feeds_speeds/machines.py`).
- **No core edits.** Adding a dialect must not require changing the generator,
  formatter, parser, or domain model. If it does, the abstraction has leaked and
  should be reconsidered.
- **Everything stays advisory.** Nothing a dialect emits is guaranteed safe to
  run; the output is an educational starting point to be verified on real
  hardware.
