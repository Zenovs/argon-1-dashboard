```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║    █████╗ ██████╗  ██████╗  ██████╗ ███╗   ██╗               ║
║   ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗████╗  ██║               ║
║   ███████║██████╔╝██║  ███╗██║   ██║██╔██╗ ██║               ║
║   ██╔══██║██╔══██╗██║   ██║██║   ██║██║╚██╗██║               ║
║   ██║  ██║██║  ██║╚██████╔╝╚██████╔╝██║ ╚████║               ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝  ╚═══╝               ║
║                                                               ║
║        D A S H B O A R D  ——  Argon ONE UP CM5               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

Ein leichtgewichtiges Dashboard fuer den **Argon ONE UP CM5 Raspberry Pi Laptop** mit Kali Linux und XFCE Desktop.

Zeigt **Batterie-Status**, **CPU-Temperatur** und **Luefter-Status** direkt in der XFCE-Taskleiste an. Bietet Steuerung von **Luefter** und **Tastaturbeleuchtung** ueber ein GTK3-Control-Panel.

![Dashboard Preview](docs/screenshot.png)

---

## ✨ Features

- 🔋 **Batterie-Anzeige** mit Prozent und Lade-Status
- 🌡️ **CPU-Temperatur** mit Farbcodierung
- 🌀 **Luefter-Anzeige** mit RPM und Geschwindigkeit
- 🔧 **Lueftersteuerung** (Auto/Manuell) ueber GTK3-Panel
- 💡 **Tastaturbeleuchtung** Ein/Aus-Steuerung
- 🎨 **Farbcodierung**: Gruen/Orange/Rot je nach Status
- 🔌 **Lade-Erkennung**: Unterschiedliche Icons fuer Laden/Entladen
- ⚡ **Leichtgewichtig**: Minimaler Ressourcenverbrauch
- 🚀 **Auto-Start**: Startet automatisch beim Booten
- 📊 **Tooltip**: Detaillierte Infos beim Hovern

### Farbcodierung

| Wert | Batterie | CPU-Temperatur | Luefter |
|------|----------|----------------|---------|
| 🟢 Gruen | ≥ 50% | ≤ 60°C | < 50% |
| 🟠 Orange | 20-49% | 61-70°C | 50-74% |
| 🔴 Rot | < 20% | > 70°C | ≥ 75% |

### Automatische Lueftersteuerung (konfigurierbar)

Die Standard-Luefter-Kurve verwendet lineare Interpolation zwischen den Punkten:

| CPU-Temperatur | Luefter-Geschwindigkeit |
|---------------|------------------------|
| ≤ 50°C | 0% (Aus) |
| 55°C | 30% |
| 60°C | 50% |
| 65°C | 75% |
| ≥ 70°C | 100% |

Zwischen den Punkten wird linear interpoliert (z.B. bei 57°C → ~40%).

#### Luefter-Kurve konfigurieren

Die Kurve ist konfigurierbar ueber `/etc/argon/fan_config.json`:

```json
{
    "fan_curve": [
        {"temp": 50, "speed": 0},
        {"temp": 55, "speed": 30},
        {"temp": 60, "speed": 50},
        {"temp": 65, "speed": 75},
        {"temp": 70, "speed": 100}
    ]
}
```

**Konfiguration aendern:**
- **GTK Control-Panel**: Klick auf Panel-Applet → Bereich "Luefter-Kurve konfigurieren"
- **Manuell**: `/etc/argon/fan_config.json` editieren (als root)
- Der Daemon laedt Aenderungen automatisch (kein Neustart noetig)

**Regeln:**
- Temperaturen muessen aufsteigend sortiert sein
- Luefter-Geschwindigkeit: 0-100%
- Mindestens 2 Punkte erforderlich
- Bei ungueliger Konfiguration wird die Standard-Kurve verwendet

---

## 📋 Voraussetzungen

- Raspberry Pi CM5 mit Argon ONE UP Gehaeuse
- Kali Linux mit XFCE Desktop
- I2C aktiviert (`raspi-config` → Interface Options → I2C)
- XFCE Genmon Plugin (`sudo apt install xfce4-genmon-plugin`)
- GTK3 fuer Control-Panel (`sudo apt install python3-gi gir1.2-gtk-3.0`)

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
2. ✅ Luefter-Konfiguration wird erstellt (`/etc/argon/fan_config.json`)
3. ✅ Daemon-Skript wird nach `/usr/local/bin/` kopiert
4. ✅ Panel-Applet wird nach `/usr/local/bin/` kopiert
5. ✅ Control-Panel wird nach `/usr/local/bin/` kopiert
6. ✅ Systemd-Service wird eingerichtet und gestartet (als root)
7. ✅ Genmon-Plugin wird automatisch zur Taskleiste hinzugefuegt

---

## 🔄 Update

```bash
cd argon-1-dashboard
sudo bash update.sh
```

Das Update-Skript:
- Pullt die neuesten Aenderungen von GitHub
- Aktualisiert alle Dateien (inkl. Control-Panel)
- Startet den Daemon neu

---

## 🗑️ Deinstallation

```bash
cd argon-1-dashboard
sudo bash uninstall.sh
```

Entfernt:
- Systemd-Service
- Alle installierten Dateien (inkl. Control-Panel)
- Genmon-Plugin aus der Taskleiste
- Temporaere Status- und Steuerdateien

---

## 🔧 Technische Details

### Architektur

```
argon_daemon.py (Systemd-Service, root)
    │
    ├── Liest I2C Bus 1, Adresse 0x64
    │   ├── Register 0x04 → Batterie-Prozent
    │   └── Register 0x0E → Lade-Status
    │
    ├── Liest /sys/class/thermal/thermal_zone0/temp → CPU-Temp
    │
    ├── Liest /sys/class/hwmon/hwmon3/fan1_input → Luefter-RPM
    │
    ├── Schreibt /sys/class/hwmon/hwmon3/pwm1 → Luefter-PWM
    │
    ├── Schreibt /sys/class/leds/default-on/brightness → Tastatur-LED
    │
    ├── Liest /etc/argon/fan_config.json → Luefter-Kurve (auto-reload)
    │
    ├── Liest /tmp/argon_dashboard_control ← Steuerbefehle
    │
    └── Schreibt /tmp/argon_dashboard_status → JSON-Status
                              │
                    argon_panel.sh (Genmon-Plugin)
                    ├── Zeigt in XFCE-Taskleiste an
                    └── Klick → argon_control.py (GTK3)
                                    │
                                    ├── Schreibt /tmp/argon_dashboard_control
                                    └── Schreibt /etc/argon/fan_config.json (via pkexec)
```

### I2C-Kommunikation

| Register | Beschreibung | Werte |
|----------|-------------|-------|
| `0x04` | Batterie-Prozent | 0-100 |
| `0x0E` | Lade-Status | < 0x80 = Laedt, ≥ 0x80 = Entlaedt |

### Hardware-Schnittstellen

| Pfad | Beschreibung | Zugriff |
|------|-------------|---------|
| `/sys/class/hwmon/hwmon3/fan1_input` | Luefter RPM | Lesen |
| `/sys/class/hwmon/hwmon3/pwm1` | Luefter PWM (0-255) | Schreiben (root) |
| `/sys/class/hwmon/hwmon3/pwm1_enable` | PWM-Modus | Schreiben (root) |
| `/sys/class/leds/default-on/brightness` | Tastatur-LED (0/1) | Schreiben (root) |
| `/etc/argon/fan_config.json` | Luefter-Kurve Konfiguration | Lesen (Daemon) / Schreiben (Control-Panel via pkexec) |

### Status-Datei (`/tmp/argon_dashboard_status`)

```json
{
    "battery_percent": 85,
    "is_charging": true,
    "cpu_temp": 42.5,
    "fan_rpm": 1200,
    "fan_speed": 30,
    "fan_mode": "auto",
    "kbd_backlight": true,
    "timestamp": 1711929600.0
}
```

### Steuer-Datei (`/tmp/argon_dashboard_control`)

```json
{
    "fan_mode": "auto",
    "fan_speed": 50,
    "kbd_backlight": true
}
```

---

## 🎮 Bedienung

### Panel-Applet
- Zeigt: 🔋 Batterie | 🌡 Temperatur | 🌀 Luefter
- **Klick** auf das Applet oeffnet das Control-Panel
- **Hover** zeigt detaillierte Infos als Tooltip

### Control-Panel (GTK3)
- **Luefter Auto-Modus**: Temperaturbasierte automatische Steuerung
- **Luefter Manuell**: Slider fuer 0-100% manuelle Geschwindigkeit
- **Luefter-Kurve konfigurieren**: 5 Temperatur-/Geschwindigkeitspunkte anpassbar
- **Tastaturbeleuchtung**: Ein/Aus-Schalter
- Status wird jede Sekunde aktualisiert
- Luefter-Kurve wird sofort vom Daemon uebernommen (kein Neustart noetig)

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

### Luefter-Steuerung funktioniert nicht

```bash
# PWM-Pfade pruefen
cat /sys/class/hwmon/hwmon3/fan1_input    # RPM lesen
cat /sys/class/hwmon/hwmon3/pwm1          # PWM-Wert lesen
cat /sys/class/hwmon/hwmon3/pwm1_enable   # PWM-Modus pruefen

# Manuell testen (als root)
echo 1 > /sys/class/hwmon/hwmon3/pwm1_enable
echo 128 > /sys/class/hwmon/hwmon3/pwm1   # 50%
```

### Tastaturbeleuchtung funktioniert nicht

```bash
# Pfad pruefen
cat /sys/class/leds/default-on/brightness

# Manuell testen (als root)
echo 1 > /sys/class/leds/default-on/brightness  # Ein
echo 0 > /sys/class/leds/default-on/brightness  # Aus
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

### Control-Panel oeffnet nicht

```bash
# GTK3 pruefen
python3 -c "import gi; gi.require_version('Gtk', '3.0')"

# Manuell starten
python3 /usr/local/bin/argon_control.py
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
│   ├── argon_daemon.py    # Python-Daemon (I2C + Temp + Luefter + LED)
│   ├── argon_panel.sh     # XFCE Genmon-Skript
│   ├── argon_control.py   # GTK3 Control-Panel (inkl. Luefter-Kurve)
│   ├── argon-dashboard.service  # Systemd-Service
│   └── fan_config.json    # Standard Luefter-Kurve
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
