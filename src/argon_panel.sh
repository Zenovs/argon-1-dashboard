#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 - XFCE Genmon Panel-Applet
# Liest JSON-Status und zeigt Batterie + Temperatur + Luefter mit Farbcodierung

STATUS_FILE="/tmp/argon_dashboard_status"

# Fallback wenn Status-Datei nicht existiert
if [ ! -f "$STATUS_FILE" ]; then
    echo "<txt><span foreground='#888888'>⏳ Warte...</span>   </txt>"
    echo "<tool>Argon Dashboard: Daemon laeuft nicht oder startet gerade...</tool>"
    exit 0
fi

# Status-Datei darf nicht aelter als 10 Sekunden sein
FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$STATUS_FILE" 2>/dev/null || echo 0) ))
if [ "$FILE_AGE" -gt 10 ]; then
    echo "<txt><span foreground='#FF4444'>⚠ Offline</span>   </txt>"
    echo "<tool>Argon Dashboard: Daemon antwortet nicht (Status ${FILE_AGE}s alt)</tool>"
    exit 0
fi

# JSON lesen - alle Werte auf einmal
eval $(python3 -c "
import json, sys
try:
    with open('$STATUS_FILE') as f:
        d = json.load(f)
    print(f'BATTERY={d.get(\"battery_percent\", -1)}')
    v = d.get('is_charging')
    if v is None:
        print('CHARGING=unknown')
    elif v:
        print('CHARGING=true')
    else:
        print('CHARGING=false')
    print(f'TEMP={d.get(\"cpu_temp\", -1)}')
    print(f'FAN_RPM={d.get(\"fan_rpm\", -1)}')
    print(f'FAN_SPEED={d.get(\"fan_speed\", 0)}')
    print(f'FAN_MODE={d.get(\"fan_mode\", \"auto\")}')
    tr = d.get('time_remaining')
    if tr is not None:
        h = int(tr // 60)
        m = int(tr % 60)
        print(f'TIME_H={h}')
        print(f'TIME_M={m}')
    else:
        print('TIME_H=')
        print('TIME_M=')
    print(f'BATTERY_STABLE={str(d.get(\"battery_stable\", False)).lower()}')
except:
    print('BATTERY=-1')
    print('CHARGING=unknown')
    print('TEMP=-1')
    print('FAN_RPM=-1')
    print('FAN_SPEED=0')
    print('FAN_MODE=auto')
    print('TIME_H=')
    print('TIME_M=')
    print('BATTERY_STABLE=false')
" 2>/dev/null)

# Batterie-Icon und Farbe bestimmen
if [ "$CHARGING" = "true" ]; then
    BATT_ICON="⚡"
else
    BATT_ICON="🔋"
fi

# Restzeit-Anzeige aufbereiten
if [ -n "$TIME_H" ]; then
    TIME_TEXT=" ${TIME_H}:$(printf '%02d' ${TIME_M})h"
else
    TIME_TEXT=""
fi

# Batterie-Farbcodierung
if [ "$BATTERY" -eq -1 ] 2>/dev/null; then
    BATT_COLOR="#888888"
    BATT_TEXT="--"
elif [ "$BATTERY" -lt 20 ]; then
    BATT_COLOR="#FF4444"  # Rot
    BATT_TEXT="${BATTERY}%"
elif [ "$BATTERY" -lt 50 ]; then
    BATT_COLOR="#FF8800"  # Orange
    BATT_TEXT="${BATTERY}%"
else
    BATT_COLOR="#44CC44"  # Gruen
    BATT_TEXT="${BATTERY}%"
fi

# Temperatur-Farbcodierung
TEMP_INT=$(printf "%.0f" "$TEMP" 2>/dev/null || echo "-1")

if [ "$TEMP_INT" -eq -1 ] 2>/dev/null; then
    TEMP_COLOR="#888888"
    TEMP_TEXT="--°C"
elif [ "$TEMP_INT" -gt 70 ]; then
    TEMP_COLOR="#FF4444"  # Rot
    TEMP_TEXT="${TEMP}°C"
elif [ "$TEMP_INT" -gt 60 ]; then
    TEMP_COLOR="#FF8800"  # Orange
    TEMP_TEXT="${TEMP}°C"
else
    TEMP_COLOR="#44CC44"  # Gruen
    TEMP_TEXT="${TEMP}°C"
fi

# Luefter-Anzeige
if [ "$FAN_RPM" -eq -1 ] 2>/dev/null; then
    FAN_TEXT="--"
    FAN_COLOR="#888888"
elif [ "$FAN_RPM" -eq 0 ] 2>/dev/null; then
    FAN_TEXT="Aus"
    FAN_COLOR="#44CC44"
else
    FAN_TEXT="${FAN_SPEED}%"
    if [ "$FAN_SPEED" -ge 75 ] 2>/dev/null; then
        FAN_COLOR="#FF4444"
    elif [ "$FAN_SPEED" -ge 50 ] 2>/dev/null; then
        FAN_COLOR="#FF8800"
    else
        FAN_COLOR="#44CC44"
    fi
fi

# Genmon XML-Ausgabe
echo "<txt>${BATT_ICON}<span foreground='${BATT_COLOR}'>${BATT_TEXT}${TIME_TEXT}</span>  <span foreground='#666666'>|</span>  🌡<span foreground='${TEMP_COLOR}'>${TEMP_TEXT}</span>  <span foreground='#666666'>|</span>  🌀<span foreground='${FAN_COLOR}'>${FAN_TEXT}</span>   </txt>"

# Click-Handler: Control-Panel oeffnen
echo "<txtclick>python3 /usr/local/bin/argon_control.py &</txtclick>"

# Tooltip mit Details
if [ "$CHARGING" = "true" ]; then
    CHARGE_TEXT="Laedt"
elif [ "$CHARGING" = "false" ]; then
    CHARGE_TEXT="Entlaedt"
else
    CHARGE_TEXT="Unbekannt"
fi

if [ "$FAN_MODE" = "auto" ]; then
    FAN_MODE_TEXT="Auto"
else
    FAN_MODE_TEXT="Manuell"
fi

FAN_RPM_TEXT="${FAN_RPM}"
[ "$FAN_RPM" -eq -1 ] 2>/dev/null && FAN_RPM_TEXT="--"

TIME_TOOLTIP=""
[ -n "$TIME_H" ] && TIME_TOOLTIP="\nRestzeit: ${TIME_H}:$(printf '%02d' ${TIME_M})h"

echo "<tool>Argon ONE UP CM5 Dashboard\n━━━━━━━━━━━━━━━━━━━━━━━\nBatterie: ${BATT_TEXT} (${CHARGE_TEXT})${TIME_TOOLTIP}\nCPU-Temp: ${TEMP_TEXT}\nLuefter: ${FAN_RPM_TEXT} RPM (${FAN_MODE_TEXT}, ${FAN_SPEED}%)\n━━━━━━━━━━━━━━━━━━━━━━━\nKlicken fuer Steuerung</tool>"
