#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 Dashboard - Deinstallationsskript
# Muss als root ausgefuehrt werden: sudo bash uninstall.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Echten Benutzer ermitteln (nicht root)
USER_NAME="${SUDO_USER:-$(logname 2>/dev/null || echo '')}"
if [ -z "$USER_NAME" ] || [ "$USER_NAME" = "root" ]; then
    echo -e "${RED}FEHLER: Konnte den aufrufenden Benutzer nicht ermitteln.${NC}"
    echo "Bitte ausfuehren mit: sudo bash uninstall.sh"
    exit 1
fi

echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  Argon ONE UP CM5 Dashboard - Deinstallation ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
echo

# Root-Check
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}FEHLER: Dieses Skript muss als root ausgefuehrt werden!${NC}"
    echo "Bitte ausfuehren mit: sudo bash uninstall.sh"
    exit 1
fi

# Bestaetigung
read -p "Wirklich deinstallieren? (j/N): " CONFIRM
if [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "J" ]; then
    echo "Abgebrochen."
    exit 0
fi

# Root-Service stoppen und deaktivieren
echo -e "${YELLOW}[1/4] Stoppe und deaktiviere Services...${NC}"
systemctl stop argon-dashboard.service 2>/dev/null || true
systemctl disable argon-dashboard.service 2>/dev/null || true
rm -f /etc/systemd/system/argon-dashboard.service
systemctl daemon-reload
echo "  → argon-dashboard.service entfernt ✓"

# User-Service (Fn-Hotkeys) stoppen und deaktivieren
USER_ID=$(id -u "$USER_NAME")
sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
    systemctl --user stop argonhotkeys.service 2>/dev/null || true
sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
    systemctl --user disable argonhotkeys.service 2>/dev/null || true
rm -f "${USER_HOME}/.config/systemd/user/argonhotkeys.service"
sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
    systemctl --user daemon-reload 2>/dev/null || true
echo "  → argonhotkeys.service entfernt ✓"

# Dateien entfernen
echo -e "${YELLOW}[2/4] Entferne Dateien...${NC}"
rm -f /usr/local/bin/argon_daemon.py
rm -f /usr/local/bin/argon_panel.sh
rm -f /usr/local/bin/argon_control.py
rm -f /usr/local/bin/argon_hotkeys.py
rm -f /tmp/argon_dashboard_status
rm -f /tmp/argon_dashboard_status.tmp
rm -f /tmp/argon_dashboard_control
rm -f /tmp/argon_dashboard_control.tmp
rm -rf /etc/argon
echo "  → Dateien entfernt ✓"

# Genmon-Plugin entfernen
echo -e "${YELLOW}[3/4] Entferne Genmon-Plugin...${NC}"
if command -v xfconf-query &>/dev/null; then
    # Finde das Plugin mit argon_panel.sh
    PLUGIN_ID=$(sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
        xfconf-query -c xfce4-panel -l -v 2>/dev/null | grep "argon_panel.sh" | grep -oP 'plugin-\K[0-9]+' || true)
    
    if [ -n "$PLUGIN_ID" ]; then
        # Plugin-Eigenschaften entfernen
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${PLUGIN_ID} -r -R 2>/dev/null || true
        
        # Plugin aus Panel-Liste entfernen
        CURRENT_PLUGINS=$(sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids 2>/dev/null || echo "")
        
        if [ -n "$CURRENT_PLUGINS" ]; then
            PLUGIN_ARGS=""
            for pid in $(echo "$CURRENT_PLUGINS" | tr '\n' ' '); do
                if [[ "$pid" =~ ^[0-9]+$ ]] && [ "$pid" != "$PLUGIN_ID" ]; then
                    PLUGIN_ARGS="$PLUGIN_ARGS -t int -s $pid"
                fi
            done
            
            if [ -n "$PLUGIN_ARGS" ]; then
                eval sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/\$(id -u $USER_NAME)/bus" \
                    xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids --create -a $PLUGIN_ARGS 2>/dev/null || true
            fi
        fi
        
        echo "  → Genmon-Plugin #${PLUGIN_ID} entfernt ✓"
        
        # Panel neu starten
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfce4-panel --restart 2>/dev/null &
    else
        echo "  → Kein Argon Genmon-Plugin gefunden"
    fi
else
    echo "  → xfconf-query nicht verfuegbar, manuelles Entfernen noetig"
fi

# Abschluss
echo -e "${YELLOW}[4/4] Aufraeumen...${NC}"
echo "  → Fertig ✓"

echo
echo -e "${GREEN}Deinstallation abgeschlossen.${NC}"
echo
echo "Hinweis: smbus2 wurde nicht deinstalliert."
echo "Falls gewuenscht: pip3 uninstall smbus2"
