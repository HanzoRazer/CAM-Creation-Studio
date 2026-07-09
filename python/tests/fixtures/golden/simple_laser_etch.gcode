; --- HEADER ---
G21 ; units = mm
G90 ; absolute positioning
M5 ; beam off
G0 Z5 ; move to safe height

; --- TOOLPATH ---
G0 X0 Y0
M3 S200
G1 X10 Y0 F600
G1 X10 Y10
G1 X0 Y10
G1 X0 Y0
M5

; --- FOOTER ---
G0 Z5 ; retract
M5 ; beam off
G0 X0 Y0 ; park
M30 ; end of program