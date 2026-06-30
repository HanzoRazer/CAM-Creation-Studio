# G-code Basics — Reading & Writing G-code for Beginners

*3D print · CNC · laser*

G-code is the plain-text language that tells a machine where to move, how fast,
and what to do when it gets there. Every line is one instruction. This guide
covers the handful of commands you actually need, the structure of a working
program, and the differences between Marlin-based 3D printers and standard CNC
mills — enough to read most files and write your first one.

> Source: adapted from the project's original *G-code Quick-Start Manual* (REV
> 1.0). The styled originals are preserved under
> [`archive/original-html/`](../archive/original-html/).

## Anatomy of a line

```text
G1 X10 Y5 Z-0.5 F800 ; first cut
```

- `G1` — command: *what to do*
- `X Y Z` — target coordinates
- `F` — feed rate (speed)
- `;` — comment, ignored by the machine

## 1 — Command reference

### Essential G-codes

| Code | Does | Typical use |
|------|------|-------------|
| `G0` | Rapid move — travel at max speed, not cutting | `G0 X0 Y0 Z5` |
| `G1` | Linear move at a set feed rate — the working move (cut / extrude) | `G1 X10 Y5 F800` |
| `G2` | Clockwise arc to a point, center via `I J` or radius via `R` | `G2 X10 Y10 I5 J0` |
| `G3` | Counter-clockwise arc — same parameters as `G2` | `G3 X0 Y10 I-5 J0` |
| `G20` / `G21` | Units: inches (`G20`) / millimetres (`G21`) | `G21` |
| `G28` | Home axes — move to a known reference (endstops / limit switches) | `G28 ; all axes` |
| `G90` / `G91` | Absolute (`G90`) / relative (`G91`) positioning | `G90` |
| `G92` | Set current position — redefine coordinates without moving | `G92 E0` |

### M-codes — machine actions

G-codes move the machine; M-codes ("miscellaneous") switch things on and off —
spindles, heaters, fans, coolant — and control program flow.

| Code | Does | Found on |
|------|------|----------|
| `M3` / `M4` | Spindle / laser on, CW (`M3`) or CCW (`M4`), at speed `S` | CNC / laser |
| `M5` | Spindle / laser off | CNC / laser |
| `M6` | Tool change (often with a `T` word, e.g. `T2`) | CNC |
| `M8` / `M9` | Coolant on / off | CNC |
| `M104` / `M109` | Set hotend temp (`M104`, don't wait) / set and wait (`M109`) | Marlin |
| `M140` / `M190` | Set bed temp (`M140`) / set and wait (`M190`) | Marlin |
| `M106` / `M107` | Part-cooling fan on (speed `S0`–`255`) / off | Marlin |
| `M84` | Disable steppers (release motors) | Marlin |
| `M2` / `M30` | End of program (`M30` also rewinds) | Both |

## 2 — File structure: header, body, footer

Almost every G-code file follows the same three-part shape. The **header** puts
the machine in a known, safe state; the **body** does the work; the **footer**
powers everything down cleanly.

```text
; --- HEADER ---
G21          ; units = mm
G90          ; absolute coords
G28          ; home all axes
M3 S12000    ; spindle on
G0 Z5        ; safe height

; --- BODY ---
G0 X0 Y0
G1 Z-0.5 F300
G1 X20 Y0 F800
G1 X20 Y20
G2 X0 Y20 I-10 J0

; --- FOOTER ---
G0 Z5        ; retract
M5           ; spindle off
G0 X0 Y0     ; park
M30          ; end
```

## 3 — Dialect differences: Marlin 3D printers vs. CNC mills

| Topic | Marlin (3D printer) | CNC mill |
|-------|---------------------|----------|
| The "tool" | Heated nozzle extruding plastic — material on the `E` axis | Rotating cutter — `M3/M4/M5` + spindle speed `S` |
| Moving = making | `G1 X.. E..` — distance and extrusion combined | `G1 X.. Z..` — cutting happens because the spindle is already on |
| Temperature | Core to every job — `M104/M109/M140/M190` | No heat codes; coolant instead (`M7/M8/M9`) |
| Feed rate `F` | mm/min (some firmware mm/s), per move | mm/min or in/min; rapids (`G0`) ignore `F` |
| Coordinate systems | Single space; origin from homing + `G92` | Work offsets `G54`–`G59` set part zero anywhere |
| Arcs (`G2/G3`) | Only if firmware built with arc support | Used heavily; `I/J` (center) or `R` (radius) |
| Tool changes | Rare — `T0/T1` on multi-extruder machines | Common — `T2 M6` swaps end mills mid-program |

## 4 — Your first program: a 5-step checklist

1. **Set the ground rules first.** Open with units (`G21`) and positioning
   (`G90`). Never assume the machine's last state.
2. **Home, then go to a safe height.** Run `G28`, then lift Z (`G0 Z5`) before
   any XY travel.
3. **Write the body in small moves.** `G0` to position, `G1` to cut/print. Put a
   feed rate `F` on your first working move.
4. **Shut down in the footer.** Retract Z, turn off spindle/heaters (`M5` /
   `M104 S0`), park, and end (`M30`).
5. **Simulate before you run.** Preview the toolpath (or air-cut above the
   stock) to catch crashes while it's still free.

## 5 — Troubleshooting

**Axis homing**

- *"Homing failed" / head slams into frame* — endstop not triggering, or wired
  open vs. closed. Check the switch lights up before the carriage reaches it.
- *Homes the wrong direction* — homing direction or motor wiring reversed.
- *Moves before homing refused* — always `G28` first; with no known origin, soft
  limits block motion.

**Speed assignment**

- *First `G1` crawls or won't move* — no `F` set yet. Set `F` on the first
  working move.
- *Everything runs 60× too fast/slow* — units mismatch (mm/min vs. mm/s) or a
  stray `G20` in an mm program.
- *Skipped steps / lost position* — feed or spindle load too high; motors stall.
  Lower `F` or depth per pass.

> **Safety first.** Keep a hand on feed-hold / emergency stop the first time you
> run any new program. G-code does exactly what it says — including the mistakes.
> See [safety-disclaimer.md](safety-disclaimer.md).
