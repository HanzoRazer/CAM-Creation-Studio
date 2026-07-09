; --- HEADER ---
G21 ; units = mm
G90 ; absolute positioning
G28 ; home all axes
M140 S60 ; set bed temp
M104 S200 ; set hotend temp
M190 S60 ; wait for bed
M109 S200 ; wait for hotend
G0 Z5 ; move to safe height

; --- BODY ---
G0 X0 Y0 Z5
G1 X40 Y0 E2 F1500
G1 X40 Y40 E4 F1500
G1 X0 Y40 E6 F1500
G1 X0 Y0 E8 F1500
G0 Z5

; --- FOOTER ---
G0 Z5 ; retract
M104 S0 ; hotend off
M140 S0 ; bed off
M84 ; disable steppers
G0 X0 Y0 ; park
M30 ; end of program