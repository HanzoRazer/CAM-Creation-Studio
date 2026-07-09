; --- HEADER ---
G21 ; units = mm
G90 ; absolute positioning
M3 S12000 ; spindle on
G0 Z5 ; move to safe height

; --- BODY ---
G0 X0 Y0 Z5
G0 X0 Y0
G1 Z-1 F800
G1 X40 F800
G1 Y40 F800
G1 X0 F800
G1 Y0 F800
G0 Z5

; --- FOOTER ---
G0 Z5 ; retract
M5 ; spindle off
G0 X0 Y0 ; park
M30 ; end of program