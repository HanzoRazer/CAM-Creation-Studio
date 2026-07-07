# Domain Model

The Python core (`python/cam_creation_studio/`) is the canonical implementation
of CAM-Creation-Studio. Its foundation is a small set of **immutable dataclasses**
that every other layer — generation, parsing, validation, and any future UI —
speaks in preference to passing raw dictionaries around.

> The browser/JS prototype under `app/` and `archive/` is historical reference
> only. Business logic is never duplicated there.

## The hierarchy

```
GCodeProgram
├── header : ProgramHeader        # units, positioning, home, machine, safe Z, startup
├── moves  : [Move | ArcMove...]  # the body — one motion instruction each
│       │
│       └── Move / ArcMove  ──(generator)──►  Line  ──►  [Word, Word, ...]  ──►  text
│
└── footer : ProgramFooter        # retract, shutdown, park, end code
```

Read top-to-bottom it is: a **Program** contains **Moves**; each Move is rendered
into a **Line**; a Line is a command plus **Words**; Words format to text. Read
bottom-up it is exactly how a generated file is assembled.

## The objects

| Object | Module | Role |
|---|---|---|
| `Point`, `Bounds` | `shared/geometry.py` | geometry primitives (re-exported from `models`) |
| `Move` | `models.py` | a linear/rapid instruction (G0/G1) |
| `ArcMove` | `models.py` | a circular-arc instruction (G2/G3) with I/J or R |
| `Diagnostic` | `models.py` | one advisory validation finding |
| `ProgramHeader` / `ProgramFooter` | `models.py` | typed description of the opening/closing block |
| `GCodeProgram` | `models.py` | header + ordered moves + footer |
| `Word`, `Line` | `gcode/words.py` | the text-formatting representation |
| `MachineProfile`, `Material`, `Tool` | `feeds_speeds/` | profile libraries (re-exported from `models`) |
| `FeedRecommendation` | `feeds_speeds/calculator.py` | advisory feeds/speeds result |

`cam_creation_studio.models` re-exports the profile objects and geometry
primitives, so a consumer needs a single import for "the shape of the domain":

```python
from cam_creation_studio.models import (
    Move, ArcMove, GCodeProgram, ProgramHeader, ProgramFooter,
    Diagnostic, Point, Bounds, MachineProfile, Material, Tool, FeedRecommendation,
)
```

## Enumerations, not bare strings

Closed sets of choices live in `enums.py`: `Units`, `MoveType`, `CutMode`,
`MachineType`, `DiagnosticSeverity`. Each is a `str`-based enum, so a member both
behaves like its wire string (`DiagnosticSeverity.DANGER == "danger"`) and
serializes to that string — existing string comparisons and JSON round-trips keep
working while callers still get real symbols to branch on.

## Immutability & equality

Every dataclass is `frozen=True` (and `slots=True` where practical). Objects are
compared by value, which makes them trivial to test and safe to share:

```python
Move(x=10, y=5) == Move(type=MoveType.LINEAR, x=10, y=5)   # True
```

Any coordinate left `None` is simply omitted from the emitted line — this is how
G-code's *modal* behavior is preserved (an unset axis holds its previous value).

## Serialization

Future GUIs, HTTP APIs, and file export move these objects across a boundary as
plain data. `shared/serialization.py` provides reflection-based `to_json` /
`from_json` that understand nested dataclasses, `str` enums, `Optional`, and
containers. `GCodeProgram` — whose `moves` is a `Move | ArcMove` union the generic
coercer can't disambiguate — owns its own `to_json` / `from_json` built on
`move_from_dict`.

```python
text = program.to_json()
same = GCodeProgram.from_json(text)      # same == program
```

## The hybrid (dict adapter) rule

Dataclasses are the **internal source of truth**. The older dict-based entry
points (`build_program(config, job)`, `format_line(...)`, `parse_program(...)`,
`validate_program(...)`) remain as **thin compatibility adapters** so existing
callers keep working — each simply builds domain objects and delegates. There are
no parallel implementations: the object path and the dict path render identical
text (verified in `tests/test_generator_model.py`).

## Machine independence

Nothing in `models.py` or `enums.py` knows about GRBL, Mach4, LinuxCNC, or Marlin.
Machine-specific behavior lives only in the dialect adapters — see
[DIALECT_SYSTEM.md](DIALECT_SYSTEM.md).
