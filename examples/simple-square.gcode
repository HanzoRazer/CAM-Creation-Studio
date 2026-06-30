; CAM-Creation-Studio example — simple CNC square (educational, verify before running)
; --- HEADER ---
G21 ; units = mm
G90 ; absolute positioning
G28 ; home all axes
M3 S12000 ; spindle on
G0 Z5 ; move to safe height

; --- BODY ---
G0 X0 Y0
G1 Z-0.5 F300
G1 X40 Y0 F800
G1 X40 Y30
G1 X0 Y30
G1 X0 Y0

; --- FOOTER ---
G0 Z5 ; retract
M5 ; spindle off
G0 X0 Y0 ; park
M30 ; end of program
