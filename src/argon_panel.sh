#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 - XFCE Genmon Panel-Applet

STATUS_FILE="/tmp/argon_dashboard_status"
NOTIF_FILE="${HOME}/.config/argon/notifications.json"
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

# JSON-Werte per grep auslesen (kein Python-Subprozess mehr noetig,
# spart einen Interpreter-Start alle 2 Sekunden im Dauerbetrieb)
json_get() {
    grep -oP "\"$2\":\s*\K[^,}]*" "$1" 2>/dev/null | head -1 | tr -d '"'
}

BATTERY=$(json_get "$STATUS_FILE" battery_percent)
BATTERY=${BATTERY%%.*}
[ -z "$BATTERY" ] && BATTERY=-1

case "$(json_get "$STATUS_FILE" is_charging)" in
    true)  CHARGING="true" ;;
    false) CHARGING="false" ;;
    *)     CHARGING="unknown" ;;
esac

TEMP=$(json_get "$STATUS_FILE" cpu_temp)
[ -z "$TEMP" ] && TEMP=-1

FAN_RPM=$(json_get "$STATUS_FILE" fan_rpm)
FAN_RPM=${FAN_RPM%%.*}
[ -z "$FAN_RPM" ] && FAN_RPM=-1

FAN_SPEED=$(json_get "$STATUS_FILE" fan_speed)
FAN_SPEED=${FAN_SPEED%%.*}
[ -z "$FAN_SPEED" ] && FAN_SPEED=0

TR_RAW=$(json_get "$STATUS_FILE" time_remaining)
if [ -n "$TR_RAW" ] && [ "$TR_RAW" != "null" ]; then
    TR_INT=${TR_RAW%%.*}
    TIME_H=$(( TR_INT / 60 ))
    TIME_M=$(( TR_INT % 60 ))
else
    TIME_H=""
    TIME_M=""
fi

BATT_WARN="false"
BATT_THRESH=10
if [ -f "$NOTIF_FILE" ]; then
    [ "$(json_get "$NOTIF_FILE" battery_warning)" = "true" ] && BATT_WARN="true"
    bt=$(json_get "$NOTIF_FILE" battery_threshold)
    [ -n "$bt" ] && BATT_THRESH=${bt%%.*}
fi

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

# Akku-Warnung (nur wenn aktiviert, nicht ladend, und Schwellenwert unterschritten)
BATT_WARN_FLAG="/tmp/argon_batt_warned"
if [ "$BATT_WARN" = "true" ] && [ "$CHARGING" != "true" ]; then
    if [ "$BATTERY" -ge 0 ] 2>/dev/null && [ "$BATTERY" -le "$BATT_THRESH" ] 2>/dev/null; then
        if [ ! -f "$BATT_WARN_FLAG" ]; then
            notify-send -u critical -i battery-caution -t 0 \
                "Akku-Warnung" "Nur noch ${BATTERY}% Akkukapazität!" 2>/dev/null || true
            touch "$BATT_WARN_FLAG"
        fi
    elif [ "$BATTERY" -gt "$((BATT_THRESH + 5))" ] 2>/dev/null; then
        rm -f "$BATT_WARN_FLAG"
    fi
fi

# Ausgabe — kein line_height, GTK zentriert den Label-Inhalt automatisch vertikal
OUTPUT="${BATT_PART}${SEP}${ICON_TEMP}<span ${TX}>${TEMP_TEXT}</span>${SEP}${ICON_FAN}<span ${TX}>${FAN_TEXT}</span>"
echo "<txt>${OUTPUT}   </txt>"
echo "<txtclick>python3 /usr/local/bin/argon_control.py &</txtclick>"
echo "<tool>Klicken fuer mehr Infos und Steuerung</tool>"
