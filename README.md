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

Ein leichtgewichtiges Dashboard fuer den **Argon ONE UP CM5 Raspberry Pi Laptop** unter Kali Linux / XFCE.

Zeigt **Batterie**, **CPU-Temperatur** und **Luefter** in der XFCE-Taskleiste. Steuerung von **Luefter**, **Bildschirmhelligkeit** und **Tastaturbeleuchtung** im GTK3-Control-Panel.

---

## ✨ Features

- 🔋 **Batterie** mit Prozent, Lade-/Entladestatus und Restzeit
- 🌡️ **CPU-Temperatur** mit Farbcodierung
- 🌀 **Luefter** mit RPM und Geschwindigkeit
- ☀️ **Bildschirmhelligkeit** per Slider oder **Fn+F2/F3** Tasten
- 🔧 **Lueftersteuerung** (Auto/Manuell) mit konfigurierbarer Kurve
- 💡 **Tastaturbeleuchtung** Ein/Aus
- 🔌 **Lade-Erkennung** direkt vom CW2217 Chip (Register 0x0E)
- ⚡ **Leichtgewichtig**: Minimaler Ressourcenverbrauch
- 🚀 **Auto-Start**: Startet automatisch beim Booten

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
    ├── I2C Bus 1, Adresse 0x64 (CW2217 Batterie-Chip)
    │   ├── Init: Batterie-Profil laden (76 Bytes, Register 0x10-0x59)
    │   ├── Register 0x04 → Batterie-Prozent (0-100%)
    │   └── Register 0x0E → Lade-Status (< 0x80 = laedt)
    │
    ├── I2C Bus 14, Adresse 0x37 (DDC/CI Display)
    │   └── VCP 0x10 → Bildschirmhelligkeit (10-100%)
    │
    ├── /sys/class/thermal/thermal_zone0/temp → CPU-Temp
    ├── /sys/class/hwmon/hwmon3/fan1_input → Luefter-RPM
    ├── /sys/class/hwmon/hwmon3/pwm1 → Luefter-PWM
    ├── /sys/class/leds/default-on/brightness → Tastatur-LED
    ├── /tmp/argon_dashboard_control ← Steuerbefehle
    └── /tmp/argon_dashboard_status → JSON-Status
                          │
                argon_panel.sh (Genmon-Plugin, XFCE Taskleiste)
                └── Klick → argon_control.py (GTK3 Control-Panel)
                                │
                                ├── Helligkeit-Slider
                                ├── Luefter Auto/Manuell + Kurve
                                └── Tastaturbeleuchtung

argon_hotkeys.py (User-Systemd-Service)
    └── evdev → KEY_BRIGHTNESSUP/DOWN (Fn+F3/F2) → Helligkeit
```

### I2C-Kommunikation

**Batterie-Chip CW2217 (Bus 1, Adresse 0x64):**

| Register | Beschreibung | Werte |
|----------|-------------|-------|
| `0x04` | Batterie-Prozent | 0-100% |
| `0x0E` | Lade-Status | < 0x80 = Laedt, ≥ 0x80 = Entlaedt |
| `0x08` | Modus-Register | 0x30=Restart, 0xF0=Sleep, 0x00=Aktiv |
| `0x10-0x59` | Batterie-Profil | 76 Bytes (Argon ONE UP spezifisch) |

**Display DDC/CI (Bus 14, Adresse 0x37):**

| VCP Code | Beschreibung | Werte |
|----------|-------------|-------|
| `0x10` | Bildschirmhelligkeit | 10-100% |

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
    "battery_rate": -2.1,
    "time_remaining": 210,
    "cpu_temp": 42.5,
    "fan_rpm": 1200,
    "fan_speed": 30,
    "fan_mode": "auto",
    "kbd_backlight": true,
    "brightness": 80,
    "timestamp": 1711929600.0
}
```

### Steuer-Datei (`/tmp/argon_dashboard_control`)

```json
{
    "fan_mode": "auto",
    "fan_speed": 50,
    "kbd_backlight": true,
    "brightness": 80
}
```

---

## 🎮 Bedienung

### Panel-Applet
- Zeigt: 🔋 Batterie | 🌡 Temperatur | 🌀 Luefter
- **Klick** auf das Applet oeffnet das Control-Panel
- **Hover** zeigt detaillierte Infos als Tooltip

### Control-Panel (GTK3)
- **☀ Bildschirmhelligkeit**: Slider 10-100% (sofort wirksam)
- **Fn+F2 / Fn+F3**: Helligkeit -/+ direkt ueber Tastatur
- **Luefter Auto-Modus**: Temperaturbasierte automatische Steuerung
- **Luefter Manuell**: Slider fuer 0-100% manuelle Geschwindigkeit
- **Luefter-Kurve konfigurieren**: 5 Temperatur-/Geschwindigkeitspunkte anpassbar
- **Tastaturbeleuchtung**: Ein/Aus-Schalter

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
│   ├── argon_daemon.py        # Daemon (I2C Batterie + DDC Helligkeit + Luefter)
│   ├── argon_panel.sh         # XFCE Genmon-Taskleisten-Applet
│   ├── argon_control.py       # GTK3 Control-Panel
│   ├── argon_hotkeys.py       # Fn+F2/F3 Helligkeits-Hotkeys (User-Service)
│   ├── argon-dashboard.service  # Systemd Root-Service
│   ├── argonhotkeys.service   # Systemd User-Service (Hotkeys)
│   └── fan_config.json        # Standard Luefter-Kurve
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
