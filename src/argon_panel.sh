#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 - XFCE Genmon Panel-Applet

STATUS_FILE="/tmp/argon_dashboard_status"
WHITE="#ffffff"
DIM="#aaaaaa"
SEP="  <span foreground='#555555'>|</span>  "

# Fallback wenn Status-Datei nicht existiert
if [ ! -f "$STATUS_FILE" ]; then
    echo "<txt><span foreground='${DIM}'>Warte...</span></txt>"
    echo "<tool>Argon Dashboard: Daemon laeuft nicht oder startet gerade...</tool>"
    exit 0
fi

# Status-Datei darf nicht aelter als 10 Sekunden sein
FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$STATUS_FILE" 2>/dev/null || echo 0) ))
if [ "$FILE_AGE" -gt 10 ]; then
    echo "<txt><span foreground='${WHITE}'>Offline</span></txt>"
    echo "<tool>Argon Dashboard: Daemon antwortet nicht (Status ${FILE_AGE}s alt)</tool>"
    exit 0
fi

# JSON lesen
eval "$(python3 << 'PYEOF'
import json, sys
try:
    with open('/tmp/argon_dashboard_status') as f:
        d = json.load(f)
    print(f'BATTERY={int(d.get("battery_percent", -1))}')
    v = d.get('is_charging')
    if v is True:
        print('CHARGING=true')
    elif v is False:
        print('CHARGING=false')
    else:
        print('CHARGING=unknown')
    print(f'TEMP={d.get("cpu_temp", -1)}')
    print(f'FAN_RPM={d.get("fan_rpm", -1)}')
    print(f'FAN_SPEED={d.get("fan_speed", 0)}')
    tr = d.get('time_remaining')
    if tr is not None:
        h = int(tr // 60)
        m = int(tr % 60)
        print(f'TIME_H={h}')
        print(f'TIME_M={m}')
    else:
        print('TIME_H=')
        print('TIME_M=')
except Exception:
    print('BATTERY=-1')
    print('CHARGING=unknown')
    print('TEMP=-1')
    print('FAN_RPM=-1')
    print('FAN_SPEED=0')
    print('TIME_H=')
    print('TIME_M=')
PYEOF
)"

# Ladeindikator
if [ "$CHARGING" = "true" ]; then
    CHARGE_SPAN="yes"
else
    CHARGE_SPAN=""
fi

# Restzeit
if [ -n "$TIME_H" ]; then
    TIME_TEXT="${TIME_H}:$(printf '%02d' ${TIME_M})h"
else
    TIME_TEXT=""
fi

# Batterie
if [ "$BATTERY" -eq -1 ] 2>/dev/null; then
    BATT_TEXT="--"
else
    BATT_TEXT="${BATTERY}%"
fi

# Temperatur
TEMP_INT=$(printf "%.0f" "$TEMP" 2>/dev/null || echo "-1")
if [ "$TEMP_INT" -eq -1 ] 2>/dev/null; then
    TEMP_TEXT="--&#xB0;C"
else
    TEMP_TEXT="${TEMP}&#xB0;C"
fi

# Luefter
if [ "$FAN_RPM" -eq -1 ] 2>/dev/null; then
    FAN_TEXT="--"
elif [ "$FAN_RPM" -eq 0 ] 2>/dev/null; then
    FAN_TEXT="Aus"
else
    FAN_TEXT="${FAN_SPEED}%"
fi

GAP="  "
IC="foreground='${WHITE}'"
TX="foreground='${WHITE}'"

# Icons weiss (Unicode, kein Emoji)
ICON_BATT="<span ${IC}>&#x25A0;</span>${GAP}"
ICON_TEMP="<span ${IC}>&#x25B2;</span>${GAP}"
ICON_FAN="<span ${IC}>&#x21BA;</span>${GAP}"

# Batterie-Bereich
BATT_PART="${ICON_BATT}<span ${TX}>${BATT_TEXT}</span>"
if [ -n "$CHARGE_SPAN" ]; then
    BATT_PART="${BATT_PART} <span ${IC}>&#x2B06;</span>"
fi
if [ -n "$TIME_TEXT" ]; then
    BATT_PART="${BATT_PART}${SEP}<span ${TX}>${TIME_TEXT}</span>"
fi

# Ausgabe — kein line_height, GTK zentriert den Label-Inhalt automatisch vertikal
OUTPUT="${BATT_PART}${SEP}${ICON_TEMP}<span ${TX}>${TEMP_TEXT}</span>${SEP}${ICON_FAN}<span ${TX}>${FAN_TEXT}</span>"
echo "<txt>${OUTPUT}   </txt>"
echo "<txtclick>python3 /usr/local/bin/argon_control.py &</txtclick>"
echo "<tool>Klicken fuer mehr Infos und Steuerung</tool>"
