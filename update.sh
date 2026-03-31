#!/bin/bash
# -*- coding: utf-8 -*-
# Argon ONE UP CM5 Dashboard - Update-Skript
# Muss als root ausgefuehrt werden: sudo bash update.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Git Pull
echo -e "${YELLOW}[1/4] Aktualisiere Repository...${NC}"
cd "$SCRIPT_DIR"
if [ -d ".git" ]; then
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ Git Pull fehlgeschlagen. Ueberspringe...${NC}"
    }
    echo "  → Repository aktualisiert ✓"
else
    echo "  → Kein Git-Repository gefunden, ueberspringe Pull"
fi

# Daemon stoppen
echo -e "${YELLOW}[2/4] Stoppe Daemon...${NC}"
systemctl stop argon-dashboard.service 2>/dev/null || true
echo "  → Daemon gestoppt ✓"

# Dateien aktualisieren
echo -e "${YELLOW}[3/4] Aktualisiere Dateien...${NC}"
cp "${SCRIPT_DIR}/src/argon_daemon.py" /usr/local/bin/argon_daemon.py
chmod 755 /usr/local/bin/argon_daemon.py
echo "  → argon_daemon.py ✓"

cp "${SCRIPT_DIR}/src/argon_panel.sh" /usr/local/bin/argon_panel.sh
chmod 755 /usr/local/bin/argon_panel.sh
echo "  → argon_panel.sh ✓"

cp "${SCRIPT_DIR}/src/argon-dashboard.service" /etc/systemd/system/argon-dashboard.service
systemctl daemon-reload
echo "  → argon-dashboard.service ✓"

# Daemon neu starten
echo -e "${YELLOW}[4/4] Starte Daemon neu...${NC}"
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
