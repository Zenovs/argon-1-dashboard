# 🔋 Argon ONE UP CM5 Dashboard

Ein leichtgewichtiges Dashboard fuer den **Argon ONE UP CM5 Raspberry Pi Laptop** mit Kali Linux und XFCE Desktop.

Zeigt **Batterie-Status** und **CPU-Temperatur** direkt in der XFCE-Taskleiste an.

![Dashboard Preview](docs/screenshot.png)

---

## ✨ Features

- 🔋 **Batterie-Anzeige** mit Prozent und Lade-Status
- 🌡️ **CPU-Temperatur** mit Farbcodierung
- 🎨 **Farbcodierung**: Gruen/Orange/Rot je nach Status
- 🔌 **Lade-Erkennung**: Unterschiedliche Icons fuer Laden/Entladen
- ⚡ **Leichtgewichtig**: Minimaler Ressourcenverbrauch
- 🚀 **Auto-Start**: Startet automatisch beim Booten
- 📊 **Tooltip**: Detaillierte Infos beim Hovern

### Farbcodierung

| Wert | Batterie | CPU-Temperatur |
|------|----------|----------------|
| 🟢 Gruen | ≥ 50% | ≤ 60°C |
| 🟠 Orange | 20-49% | 61-70°C |
| 🔴 Rot | < 20% | > 70°C |

---

## 📋 Voraussetzungen

- Raspberry Pi CM5 mit Argon ONE UP Gehaeuse
- Kali Linux mit XFCE Desktop
- I2C aktiviert (`raspi-config` → Interface Options → I2C)
- XFCE Genmon Plugin (`sudo apt install xfce4-genmon-plugin`)

---

## 🚀 Installation

### 1-Befehl-Installation

```bash
git clone https://github.com/Zenovs/argon-1-dashboard.git
cd argon-1-dashboard
sudo bash install.sh
```

### Was passiert bei der Installation?

1. ✅ `smbus2` Python-Paket wird installiert
2. ✅ Daemon-Skript wird nach `/usr/local/bin/` kopiert
3. ✅ Panel-Applet wird nach `/usr/local/bin/` kopiert
4. ✅ Systemd-Service wird eingerichtet und gestartet
5. ✅ Genmon-Plugin wird automatisch zur Taskleiste hinzugefuegt

---

## 🔄 Update

```bash
cd argon-1-dashboard
sudo bash update.sh
```

Das Update-Skript:
- Pullt die neuesten Aenderungen von GitHub
- Aktualisiert alle Dateien
- Startet den Daemon neu

---

## 🗑️ Deinstallation

```bash
cd argon-1-dashboard
sudo bash uninstall.sh
```

Entfernt:
- Systemd-Service
- Alle installierten Dateien
- Genmon-Plugin aus der Taskleiste

---

## 🔧 Technische Details

### Architektur

```
argon_daemon.py (Systemd-Service)
    │
    ├── Liest I2C Bus 1, Adresse 0x64
    │   ├── Register 0x04 → Batterie-Prozent
    │   └── Register 0x0E → Lade-Status
    │
    ├── Liest /sys/class/thermal/thermal_zone0/temp
    │
    └── Schreibt JSON → /tmp/argon_dashboard_status
                              │
                    argon_panel.sh (Genmon-Plugin)
                              │
                    Zeigt in XFCE-Taskleiste an
```

### I2C-Kommunikation

| Register | Beschreibung | Werte |
|----------|-------------|-------|
| `0x04` | Batterie-Prozent | 0-100 |
| `0x0E` | Lade-Status | < 0x80 = Laedt, ≥ 0x80 = Entlaedt |

### Status-Datei (`/tmp/argon_dashboard_status`)

```json
{
    "battery_percent": 85,
    "is_charging": true,
    "cpu_temp": 42.5,
    "timestamp": 1711929600.0
}
```

---

## 🛠️ Troubleshooting

### Daemon laeuft nicht

```bash
# Status pruefen
sudo systemctl status argon-dashboard

# Logs anzeigen
sudo journalctl -u argon-dashboard -f

# Manuell starten zum Testen
sudo python3 /usr/local/bin/argon_daemon.py
```

### I2C-Fehler

```bash
# I2C pruefen
ls /dev/i2c-*

# Geraete scannen
i2cdetect -y 1

# Batterie-Register manuell lesen
i2cget -y 1 0x64 0x04  # Batterie-Prozent
i2cget -y 1 0x64 0x0e  # Lade-Status
```

### Panel-Applet wird nicht angezeigt

1. Pruefen ob Genmon installiert ist:
   ```bash
   sudo apt install xfce4-genmon-plugin
   ```
2. Manuell hinzufuegen:
   - Rechtsklick auf Taskleiste → Panel → Elemente hinzufuegen
   - "Generischer Monitor" (Genmon) waehlen
   - Befehl: `/usr/local/bin/argon_panel.sh`
   - Aktualisierung: 2000 ms

### Keine Berechtigung fuer I2C

```bash
# User zur i2c-Gruppe hinzufuegen
sudo usermod -aG i2c zenovs

# Abmelden und neu anmelden oder:
newgrp i2c
```

---

## 📁 Projektstruktur

```
argon-dashboard/
├── README.md              # Diese Dokumentation
├── install.sh             # Installationsskript
├── update.sh              # Update-Skript
├── uninstall.sh           # Deinstallationsskript
├── src/
│   ├── argon_daemon.py    # Python-Daemon (I2C + Temp)
│   ├── argon_panel.sh     # XFCE Genmon-Skript
│   └── argon-dashboard.service  # Systemd-Service
└── .gitignore
```

---

## 📜 Lizenz

MIT License - Frei verwendbar und anpassbar.

---

## 🤝 Beitragen

Pull Requests und Issues sind willkommen!

1. Fork erstellen
2. Feature-Branch: `git checkout -b feature/mein-feature`
3. Commit: `git commit -m 'Neues Feature'`
4. Push: `git push origin feature/mein-feature`
5. Pull Request erstellen
