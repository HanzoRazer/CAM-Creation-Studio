




Quick-Start Manual
Reading & Writing
G-code
REV 1.0
FOR BEGINNERS
3D PRINT · CNC
G-code is the plain-text language that tells a machine where to move, how fast, and what to do when it gets there. Every line is one instruction. This guide covers the handful of commands you actually need, the structure of a working program, and the differences between Marlin-based 3D printers and standard CNC mills — enough to read most files and write your first one.

Anatomy of a line
G1 X10 Y5 Z-0.5 F800 ; first cut
G1  command — what to do
X Y Z  target coordinates
F  feed rate (speed)
;  comment, ignored
01 — Command Reference
Essential commands
Code	Does	Typical use
G0	Rapid move — travel at max speed, not cutting	G0 X0 Y0 Z5
G1	Linear move at a set feed rate — the working move (cut / extrude)	G1 X10 Y5 F800
G2	Clockwise arc to a point, radius/center via I J or R	G2 X10 Y10 I5 J0
G3	Counter-clockwise arc — same parameters as G2	G3 X0 Y10 I-5 J0
G21	Set units to millimetres (G20 = inches)	G21
G28	Home axes — move to known reference (endstops / limit switches)	G28 ; all axes
G90	Absolute positioning — coordinates are from origin (G91 = relative)	G90
G92	Set current position — redefine coordinates without moving	G92 E0
M-codes — machine actions
G-codes move the machine; M-codes (“miscellaneous”) switch things on and off — spindles, heaters, fans, coolant — and control program flow.

Code	Does	Found on
M3 / M4	Spindle / laser on, clockwise (M3) or counter-clockwise (M4), at speed S	CNC
M5	Spindle / laser off	CNC
M6	Tool change (often pairs with T-word, e.g. T2)	CNC
M8 / M9	Coolant on / off	CNC
M104 / M109	Set hotend temp (M104, don’t wait) / set and wait (M109)	Marlin
M140 / M190	Set bed temp (M140) / set and wait (M190)	Marlin
M106 / M107	Part-cooling fan on (with speed S0–255) / off	Marlin
M84	Disable steppers (release motors)	Marlin
M2 / M30	End of program (M30 also rewinds)	Both
02 — File Structure
Header, body, footer
Almost every G-code file follows the same three-part shape. The header puts the machine in a known, safe state; the body does the work; the footer powers everything down cleanly.

Header
Set units & positioning mode, home the axes, heat up or start the spindle, move to a safe start point.
Body
The actual toolpath — the sequence of G0/G1/G2/G3 moves that cut or print the part.
Footer
Retract, turn off spindle/heaters/fans, park the head out of the way, end the program.
; --- HEADER ---
G21          ; units = mm
G90          ; absolute coords
G28          ; home all axes
M3 S12000    ; spindle on
G0 Z5        ; safe height; --- BODY ---
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
03 — Dialect Differences
Marlin 3D printers vs. CNC mills
Topic	Marlin (3D printer)	CNC mill
The “tool”	Heated nozzle extruding plastic — material fed via the E axis	Rotating cutter — controlled with M3/M4/M5 + spindle speed S
Moving = making	G1 X.. E.. — distance and extrusion combined on one line	G1 X.. Z.. — cutting happens because the spindle is already on
Temperature	Core to every job — M104/M109/M140/M190	No heat codes; coolant instead (M7/M8/M9)
Feed rate F	mm/min (some firmware mm/s) — set per move	mm/min or in/min; rapids (G0) ignore F
Coordinate systems	Single space; origin set by homing + G92	Work offsets G54–G59 let you set part zero anywhere
Arcs (G2/G3)	Supported only if firmware built with arc support; many slicers avoid them	Used heavily; I/J (center) or R (radius) standard
Tool changes	Rare — T0/T1 only on multi-extruder machines	Common — T2 M6 swaps end mills mid-program
04 — Your First Program
A 5-step checklist
1
Set the ground rules first
Open with units (G21) and positioning mode (G90). Never assume the machine’s last state.
2
Home, then go to a safe height
Run G28 so the machine knows where it is, then lift Z (G0 Z5) before any XY travel.
3
Write the body in small moves
Use G0 to position, G1 to cut/print. Put a feed rate F on your first working move.
4
Shut down in the footer
Retract Z, turn off the spindle/heaters (M5 / M104 S0), park, and end (M30).
5
Simulate before you run
Preview the toolpath in a viewer (or air-cut above the stock) to catch crashes while it’s still free.
05 — Troubleshooting
Homing & speed errors
Axis homing
“Homing failed” / head slams into frame. Endstop not triggering or wired open vs. closed — check the switch lights up before the carriage hits it.
Homes the wrong direction. Homing direction or motor wiring reversed; the axis drives away from the switch.
Moves before homing are ignored or refused. Always G28 first — with no known origin, soft limits block motion.
Speed assignment
First G1 crawls or won’t move. No F set yet — feed defaults to 0 or the last value. Set F on the first working move.
Everything runs 60× too fast/slow. Units mismatch — mm/min vs. mm/s, or a stray G20 (inches) in an mm program.
Skipped steps / lost position. Feed or spindle load too high — motors stall. Lower F or depth per pass.
Safety first. Keep a hand on the feed-hold / emergency stop the first time you run any new program. G-code does exactly what it says — including the mistakes.



