; CAM-Creation-Studio example — Marlin single extruded line (educational, verify before running)
; --- HEADER ---
G21 ; units = mm
G90 ; absolute positioning
G28 ; home all axes
M140 S60 ; set bed temp
M104 S210 ; set hotend temp
M190 S60 ; wait for bed
M109 S210 ; wait for hotend
G0 Z5 ; move to safe height

; --- BODY ---
G0 X0 Y0
G1 X60 Y0 E2 F1200

; --- FOOTER ---
G0 Z5 ; retract
M104 S0 ; hotend off
M140 S0 ; bed off
M84 ; disable steppers
G0 X0 Y0 ; park
M30 ; end of program
