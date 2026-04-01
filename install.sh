#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 Dashboard - Installationsskript
# Muss als root ausgefuehrt werden: sudo bash install.sh

set -e

# Farben fuer Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

USER_NAME="zenovs"
USER_HOME="/home/zenovs"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Argon ONE UP CM5 Dashboard - Installation   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo

# ── Root-Check ──────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}FEHLER: Dieses Skript muss als root ausgefuehrt werden!${NC}"
    echo "Bitte ausfuehren mit: sudo bash install.sh"
    exit 1
fi

# ── Pruefen ob User existiert ───────────────────────────────
if ! id "$USER_NAME" &>/dev/null; then
    echo -e "${RED}FEHLER: Benutzer '$USER_NAME' existiert nicht!${NC}"
    exit 1
fi

# ── Abhaengigkeiten installieren ────────────────────────────
echo -e "${YELLOW}[1/6] Installiere Abhaengigkeiten...${NC}"
apt-get update -qq 2>/dev/null || true

# smbus2 installieren
if ! python3 -c "import smbus2" 2>/dev/null; then
    echo "  → Installiere smbus2..."
    pip3 install smbus2 --break-system-packages 2>/dev/null || pip3 install smbus2
else
    echo "  → smbus2 bereits installiert ✓"
fi

# i2c-tools pruefen
if ! command -v i2cdetect &>/dev/null; then
    echo "  → Installiere i2c-tools..."
    apt-get install -y i2c-tools
else
    echo "  → i2c-tools bereits installiert ✓"
fi

# xfce4-genmon-plugin pruefen und installieren
if ! dpkg -l xfce4-genmon-plugin &>/dev/null; then
    echo "  → Installiere xfce4-genmon-plugin..."
    apt-get install -y xfce4-genmon-plugin
else
    echo "  → xfce4-genmon-plugin bereits installiert ✓"
fi

# xfconf pruefen und installieren
if ! command -v xfconf-query &>/dev/null; then
    echo "  → Installiere xfconf..."
    apt-get install -y xfconf
else
    echo "  → xfconf bereits installiert ✓"
fi

# Sicherstellen dass User in i2c-Gruppe ist
if ! groups "$USER_NAME" | grep -q "\bi2c\b"; then
    echo "  → Fuege $USER_NAME zur i2c-Gruppe hinzu..."
    usermod -aG i2c "$USER_NAME" 2>/dev/null || true
fi

# ── Luefter-Konfiguration erstellen ──────────────────────────
echo -e "${YELLOW}[2/8] Erstelle Luefter-Konfiguration...${NC}"
mkdir -p /etc/argon
if [ ! -f /etc/argon/fan_config.json ]; then
    cp "${SCRIPT_DIR}/src/fan_config.json" /etc/argon/fan_config.json
    chmod 644 /etc/argon/fan_config.json
    chown root:root /etc/argon/fan_config.json
    echo "  → /etc/argon/fan_config.json erstellt ✓"
else
    echo "  → /etc/argon/fan_config.json bereits vorhanden ✓"
fi

# ── Dateien kopieren ────────────────────────────────────────
echo -e "${YELLOW}[3/8] Kopiere Daemon-Skript...${NC}"
cp "${SCRIPT_DIR}/src/argon_daemon.py" /usr/local/bin/argon_daemon.py
chmod 755 /usr/local/bin/argon_daemon.py
echo "  → /usr/local/bin/argon_daemon.py ✓"

echo -e "${YELLOW}[4/8] Kopiere Panel-Applet...${NC}"
cp "${SCRIPT_DIR}/src/argon_panel.sh" /usr/local/bin/argon_panel.sh
chmod 755 /usr/local/bin/argon_panel.sh
echo "  → /usr/local/bin/argon_panel.sh ✓"

echo -e "${YELLOW}[5/8] Kopiere Control-Panel...${NC}"
cp "${SCRIPT_DIR}/src/argon_control.py" /usr/local/bin/argon_control.py
chmod 755 /usr/local/bin/argon_control.py
echo "  → /usr/local/bin/argon_control.py ✓"

# ── Systemd-Service einrichten ──────────────────────────────
echo -e "${YELLOW}[6/8] Richte Systemd-Service ein...${NC}"
cp "${SCRIPT_DIR}/src/argon-dashboard.service" /etc/systemd/system/argon-dashboard.service
systemctl daemon-reload
systemctl enable argon-dashboard.service
systemctl restart argon-dashboard.service
echo "  → argon-dashboard.service aktiviert und gestartet ✓"

# ── Genmon-Plugin zur XFCE-Taskleiste hinzufuegen ──────────
echo -e "${YELLOW}[7/8] Konfiguriere XFCE-Panel Genmon-Plugin...${NC}"

# xfconf-query muss als User ausgefuehrt werden
if command -v xfconf-query &>/dev/null; then
    # Aktuelle Plugin-IDs ermitteln
    PLUGIN_IDS=$(sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
        xfconf-query -c xfce4-panel -p /plugins -l 2>/dev/null | grep -oP 'plugin-\K[0-9]+' | sort -n | tail -1)
    
    if [ -n "$PLUGIN_IDS" ]; then
        NEW_ID=$((PLUGIN_IDS + 1))
    else
        NEW_ID=50
    fi

    # Pruefen ob bereits ein Argon-Genmon existiert
    EXISTING=$(sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
        xfconf-query -c xfce4-panel -l -v 2>/dev/null | grep "argon_panel.sh" || true)
    
    if [ -z "$EXISTING" ]; then
        # Neues Genmon-Plugin erstellen
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID} -t string -s genmon --create 2>/dev/null || true
        
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID}/command -t string -s "/usr/local/bin/argon_panel.sh" --create 2>/dev/null || true
        
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID}/update-period -t int -s 2000 --create 2>/dev/null || true
        
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID}/enable-single-row -t bool -s true --create 2>/dev/null || true
        
        # Label "(genmon)" deaktivieren
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID}/use-label -t bool -s false --create 2>/dev/null || true
        
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /plugins/plugin-${NEW_ID}/text -t string -s "" --create 2>/dev/null || true

        # Plugin zur Panel-Liste hinzufuegen
        CURRENT_PLUGINS=$(sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids 2>/dev/null || echo "")
        
        if [ -n "$CURRENT_PLUGINS" ]; then
            # Plugin-IDs als Array zusammenbauen
            PLUGIN_ARGS=""
            for pid in $(echo "$CURRENT_PLUGINS" | tr '\n' ' '); do
                # Nur numerische Werte
                if [[ "$pid" =~ ^[0-9]+$ ]]; then
                    PLUGIN_ARGS="$PLUGIN_ARGS -t int -s $pid"
                fi
            done
            PLUGIN_ARGS="$PLUGIN_ARGS -t int -s $NEW_ID"
            
            eval sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/\$(id -u $USER_NAME)/bus" \
                xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids --create -a $PLUGIN_ARGS 2>/dev/null || true
        fi
        
        echo "  → Genmon-Plugin #${NEW_ID} hinzugefuegt ✓"
        
        # Panel neu starten
        sudo -u "$USER_NAME" DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u $USER_NAME)/bus" \
            xfce4-panel --restart 2>/dev/null &
    else
        echo "  → Genmon-Plugin bereits vorhanden ✓"
    fi
else
    echo -e "  ${YELLOW}⚠ xfconf-query nicht gefunden. Installiere mit:${NC}"
    echo "    sudo apt install xfconf"
    echo
    echo "  Manuelles Hinzufuegen des Panel-Applets:"
    echo "  1. Rechtsklick auf XFCE-Taskleiste → Panel → Elemente hinzufuegen"
    echo "  2. 'Generischer Monitor' (Genmon) hinzufuegen"
    echo "  3. Befehl: /usr/local/bin/argon_panel.sh"
    echo "  4. Aktualisierung: 2 Sekunden"
fi

# ── Abschluss ───────────────────────────────────────────────
echo -e "${YELLOW}[8/8] Pruefe Installation...${NC}"
sleep 2

if systemctl is-active --quiet argon-dashboard.service; then
    echo -e "  → Daemon laeuft ✓"
else
    echo -e "  ${RED}⚠ Daemon laeuft nicht! Pruefe mit: sudo systemctl status argon-dashboard${NC}"
fi

if [ -f "/tmp/argon_dashboard_status" ]; then
    echo -e "  → Status-Datei vorhanden ✓"
    echo "  → Aktueller Status:"
    python3 -c "
import json
with open('/tmp/argon_dashboard_status') as f:
    d = json.load(f)
print(f'    Batterie: {d.get(\"battery_percent\", \"?\")}%')
print(f'    Laedt: {d.get(\"is_charging\", \"?\")}')
print(f'    CPU-Temp: {d.get(\"cpu_temp\", \"?\")}°C')
print(f'    Luefter: {d.get(\"fan_rpm\", \"?\")} RPM ({d.get(\"fan_speed\", \"?\")}%, {d.get(\"fan_mode\", \"?\")})')
print(f'    Tastatur-LED: {d.get(\"kbd_backlight\", \"?\")}')
" 2>/dev/null || echo "  → Status-Datei noch nicht bereit"
else
    echo "  → Status-Datei wird in wenigen Sekunden erstellt..."
fi

echo
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation abgeschlossen! 🎉              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo
echo "Falls das Panel-Applet nicht automatisch erscheint:"
echo "  1. Rechtsklick auf Taskleiste → Panel → Elemente hinzufuegen"
echo "  2. 'Generischer Monitor' (Genmon) hinzufuegen"
echo "  3. Befehl: /usr/local/bin/argon_panel.sh"
echo "  4. Aktualisierung: 2000 ms"
echo
echo "Service-Status: sudo systemctl status argon-dashboard"
echo "Logs anzeigen:  sudo journalctl -u argon-dashboard -f"
