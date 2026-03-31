#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 - XFCE Genmon Panel-Applet
# Liest JSON-Status und zeigt Batterie + Temperatur mit Farbcodierung

STATUS_FILE="/tmp/argon_dashboard_status"

# Fallback wenn Status-Datei nicht existiert
if [ ! -f "$STATUS_FILE" ]; then
    echo "<txt><span foreground='#888888'>⏳ Warte...</span></txt>"
    echo "<tool>Argon Dashboard: Daemon laeuft nicht oder startet gerade...</tool>"
    exit 0
fi

# Status-Datei darf nicht aelter als 10 Sekunden sein
FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$STATUS_FILE" 2>/dev/null || echo 0) ))
if [ "$FILE_AGE" -gt 10 ]; then
    echo "<txt><span foreground='#FF4444'>⚠ Offline</span></txt>"
    echo "<tool>Argon Dashboard: Daemon antwortet nicht (Status ${FILE_AGE}s alt)</tool>"
    exit 0
fi

# JSON lesen
BATTERY=$(python3 -c "
import json, sys
try:
    with open('$STATUS_FILE') as f:
        d = json.load(f)
    print(d.get('battery_percent', -1))
except:
    print(-1)
" 2>/dev/null)

CHARGING=$(python3 -c "
import json, sys
try:
    with open('$STATUS_FILE') as f:
        d = json.load(f)
    v = d.get('is_charging')
    if v is None:
        print('unknown')
    elif v:
        print('true')
    else:
        print('false')
except:
    print('unknown')
" 2>/dev/null)

TEMP=$(python3 -c "
import json, sys
try:
    with open('$STATUS_FILE') as f:
        d = json.load(f)
    print(d.get('cpu_temp', -1))
except:
    print(-1)
" 2>/dev/null)

# Batterie-Icon und Farbe bestimmen
if [ "$CHARGING" = "true" ]; then
    BATT_ICON="🔌"
else
    BATT_ICON="🔋"
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
# Bash kann keine Floats vergleichen, daher als Integer (abgerundet)
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

# Genmon XML-Ausgabe
echo "<txt>${BATT_ICON}<span foreground='${BATT_COLOR}'>${BATT_TEXT}</span> 🌡<span foreground='${TEMP_COLOR}'>${TEMP_TEXT}</span></txt>"

# Tooltip mit Details
if [ "$CHARGING" = "true" ]; then
    CHARGE_TEXT="Laedt"
elif [ "$CHARGING" = "false" ]; then
    CHARGE_TEXT="Entlaedt"
else
    CHARGE_TEXT="Unbekannt"
fi

echo "<tool>Argon ONE UP CM5 Dashboard\n━━━━━━━━━━━━━━━━━━━━━━━\nBatterie: ${BATT_TEXT} (${CHARGE_TEXT})\nCPU-Temp: ${TEMP_TEXT}</tool>"
