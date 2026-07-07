# G-code Pipeline

The core turns a typed program into G-code text and back again. The two halves
are inverses at the level of the program body, which is what makes the output
trustworthy to reason about.

```
GCodeProgram ──► Generator ──► Formatter ──► text ──► Parser ──► GCodeProgram
   (objects)      header/       Line/Word     (str)    Move/ArcMove   (objects)
                  body/footer
```

## Generation

`gcode/generator.py` orchestrates only — it contains no formatting logic. The
actual section construction is split by concern:

| Module | Builds | Object entry point | Dict adapter |
|---|---|---|---|
| `gcode/header.py` | units, positioning, home, dialect startup, safe-Z rapid | `header_lines(ProgramHeader)` | `build_header(config)` |
| `gcode/body.py` | motion instructions / etch toolpaths | `body_lines_from_moves(moves)` | `build_manual_body`, `build_etch_body` |
| `gcode/footer.py` | retract, dialect shutdown, park, end code | `footer_lines(ProgramFooter)` | `build_footer(config)` |

Two ways in, one renderer:

```python
# Object path
program = program_from_config(config, [Move(...), ArcMove(...)])
text = program_to_text(program)

# Dict adapter (preserves the browser-prototype behavior byte-for-byte)
text = build_program(config, {"mode": "manual", "moves": [...]})
```

Both paths funnel through the **formatter**, so they produce identical text.

## Formatting

`gcode/words.py` + `gcode/formatter.py` are the single place that decides
spacing, number rounding, and comment style.

```
Word("X", 10.5)                         →  "X10.5"
Line("G1", [Word("X", 10)], "cut")      →  "G1 X10 ; cut"
```

- `Word.render()` formats one address+value (numbers are rounded and lose a
  trailing `.0`, so `10.0` prints as `10`).
- `Line.render()` joins the command, its words, and an optional `; comment`.
- `Line.of(command, {letter: value}, comment)` builds a Line from a mapping,
  dropping any word whose value is `None` or `""`. This is the bridge the dict
  adapters cross.
- `format_line(command, words, comment)` is the legacy adapter: it just builds a
  `Line` and renders it.

## Parsing

`gcode/parser.py` reads text back at two levels:

1. **Lexical** — `parse_line` / `parse_program` produce `ParsedLine` objects
   (raw words + comment). This is a forgiving lexer: it understands words and
   `;` / `( )` comments, not machine semantics.
2. **Domain** — `move_from_line`, `parse_moves`, and `parse_program_model` lift
   motion lines into `Move` / `ArcMove` / `GCodeProgram`. Feed is read from the
   line itself (no modal carry-over), which is exactly what round-tripping
   generated output needs.

## Round-trip guarantee

The body of a generated program parses back into the same typed moves:

```python
text  = "\n".join(render(l) for l in body_lines_from_moves(moves))
assert parse_moves(text) == moves        # tests/test_generator_model.py
```

Round-trip fidelity is defined at the **move** level. Header/footer facts that
plain G-code encodes (units, positioning, home, end code) are inferred on parse;
the machine *dialect* is not encoded in G-code text, so it is left at the model
default when reading a file back.

## What the pipeline is not

Generated output is an **educational starting point**, not a certified
post-processor, and is not guaranteed safe to run. Validation
([see the validator](../../python/cam_creation_studio/gcode/validator/)) is
advisory and never blocks generation. Always verify a program before running it
on real hardware.
