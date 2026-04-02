#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 Dashboard - Update-Skript
# Verwendung: curl -fsSL https://raw.githubusercontent.com/Zenovs/argon-1-dashboard/main/update.sh | sudo bash
# Oder lokal: sudo bash update.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO="Zenovs/argon-1-dashboard"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Argon ONE UP CM5 Dashboard - Update         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo

# Root-Check
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}FEHLER: Dieses Skript muss als root ausgefuehrt werden!${NC}"
    echo "Bitte ausfuehren mit: sudo bash update.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"

# Bestimme ob lokales Repo vorhanden ist
USE_LOCAL=false
if [ -f "${SCRIPT_DIR}/src/argon_daemon.py" ]; then
    USE_LOCAL=true
fi

# Hilfsfunktion: Datei aus GitHub laden oder lokal kopieren
fetch_file() {
    local src_path="$1"   # relativer Pfad im Repo (z.B. src/argon_daemon.py)
    local dest="$2"        # Zieldatei
    local mode="$3"        # chmod-Wert

    if [ "$USE_LOCAL" = true ]; then
        cp "${SCRIPT_DIR}/${src_path}" "$dest"
    else
        curl -fsSL "${RAW_BASE}/${src_path}" -o "$dest"
    fi
    chmod "$mode" "$dest"
}

# Git Pull (nur wenn lokales Repo vorhanden)
echo -e "${YELLOW}[1/5] Aktualisiere Repository...${NC}"
if [ "$USE_LOCAL" = true ] && [ -d "${SCRIPT_DIR}/.git" ]; then
    cd "$SCRIPT_DIR"
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ Git Pull fehlgeschlagen. Ueberspringe...${NC}"
    }
    echo "  → Repository aktualisiert ✓"
else
    echo "  → Lade Dateien von GitHub (${REPO})..."
fi

# Daemon stoppen
echo -e "${YELLOW}[2/5] Stoppe Daemon...${NC}"
systemctl stop argon-dashboard.service 2>/dev/null || true
echo "  → Daemon gestoppt ✓"

# Dateien aktualisieren
echo -e "${YELLOW}[3/5] Aktualisiere Dateien...${NC}"

fetch_file "src/argon_daemon.py"  /usr/local/bin/argon_daemon.py  755
echo "  → argon_daemon.py ✓"

fetch_file "src/argon_panel.sh"   /usr/local/bin/argon_panel.sh   755
echo "  → argon_panel.sh ✓"

fetch_file "src/argon_control.py" /usr/local/bin/argon_control.py 755
echo "  → argon_control.py ✓"

fetch_file "src/argon-dashboard.service" /etc/systemd/system/argon-dashboard.service 644
systemctl daemon-reload
echo "  → argon-dashboard.service ✓"

# Luefter-Konfiguration (nur erstellen falls nicht vorhanden)
echo -e "${YELLOW}[4/5] Pruefe Luefter-Konfiguration...${NC}"
mkdir -p /etc/argon
if [ ! -f /etc/argon/fan_config.json ]; then
    fetch_file "src/fan_config.json" /etc/argon/fan_config.json 644
    chown root:root /etc/argon/fan_config.json
    echo "  → /etc/argon/fan_config.json erstellt ✓"
else
    echo "  → /etc/argon/fan_config.json bereits vorhanden (beibehalten) ✓"
fi

# Daemon neu starten
echo -e "${YELLOW}[5/5] Starte Daemon neu...${NC}"
systemctl start argon-dashboard.service
echo "  → Daemon gestartet ✓"

# Pruefen
sleep 2
if systemctl is-active --quiet argon-dashboard.service; then
    echo
    echo -e "${GREEN}Update erfolgreich! Daemon laeuft. ✓${NC}"
else
    echo
    echo -e "${RED}⚠ Daemon laeuft nicht! Pruefe: sudo systemctl status argon-dashboard${NC}"
fi
