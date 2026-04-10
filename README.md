# Argon ONE UP CM5 Dashboard

> Battery · Fan · Brightness · Temperature monitor and controller for the **Argon ONE UP CM5 Raspberry Pi laptop** running **Kali Linux / XFCE**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20CM5-red.svg)](https://www.raspberrypi.com/products/compute-module-5/)
[![OS](https://img.shields.io/badge/OS-Kali%20Linux%20XFCE-557C94.svg)](https://www.kali.org/)
[![Python](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)

---

## One-command install

```bash
git clone https://github.com/Zenovs/argon-1-dashboard.git
cd argon-1-dashboard
sudo bash install.sh
```

Or without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/Zenovs/argon-1-dashboard/main/update.sh | sudo bash
```

---

## What it does

A lightweight XFCE panel applet + GTK3 control panel that monitors and controls the Argon ONE UP CM5 laptop hardware:

| Feature | Details |
|---|---|
| 🔋 Battery | Percentage, charge/discharge status, time remaining (via CW2217 chip) |
| 🌡 CPU Temperature | Live reading with color-coded warnings |
| 🌀 Fan | RPM display, auto/manual mode, configurable temperature curve |
| ☀️ Screen Brightness | Slider + **Fn+F2/F3** hotkeys (via DDC/CI on I2C bus 14) |
| 💡 Keyboard Backlight | On/Off toggle |
| 🖥 Panel Applet | XFCE Genmon plugin showing all values in the taskbar |

---

## Screenshots

**Panel applet** (XFCE taskbar):
```
■ 72%  ⬆  |  1:23h  |  ▲ 44°C  |  ↺ 40%
```

**Control panel** (GTK3, dark theme):
- Status overview (battery, temperature, fan, charge state, remaining time)
- Brightness slider (10–100%, synced with Fn keys)
- Fan control (Auto / Manual + configurable curve)
- Keyboard backlight toggle
- Lid action selector (suspend / hibernate / ignore)
- Screen lock on resume toggle
- One-click update button

---

## Requirements

- **Hardware**: Raspberry Pi CM5 in an Argon ONE UP enclosure
- **OS**: Kali Linux (or any Debian-based distro) with XFCE desktop
- **I2C**: Enabled via `raspi-config` → Interface Options → I2C
- **Packages** (installed automatically):
  - `python3-smbus2` / `smbus2`
  - `xfce4-genmon-plugin`
  - `python3-gi` (GTK3 bindings)
  - `evdev` (hotkey daemon)
  - `i2c-tools`

---

## Installation

```bash
git clone https://github.com/Zenovs/argon-1-dashboard.git
cd argon-1-dashboard
sudo bash install.sh
```

The install script automatically:
1. Installs all dependencies (`smbus2`, `evdev`, `xfce4-genmon-plugin`)
2. Copies scripts to `/usr/local/bin/`
3. Creates fan config at `/etc/argon/fan_config.json`
4. Sets up and starts the systemd root service (`argon-dashboard`)
5. Sets up the systemd user service for Fn hotkeys (`argonhotkeys`)
6. Adds the Genmon panel applet to the XFCE taskbar automatically

## Update

```bash
sudo bash update.sh
# or remotely:
curl -fsSL https://raw.githubusercontent.com/Zenovs/argon-1-dashboard/main/update.sh | sudo bash
```

## Uninstall

```bash
sudo bash uninstall.sh
```

---

## Fan curve configuration

Edit `/etc/argon/fan_config.json` or use the control panel UI:

```json
{
    "fan_curve": [
        {"temp": 40, "speed": 0},
        {"temp": 50, "speed": 40},
        {"temp": 60, "speed": 70},
        {"temp": 70, "speed": 100}
    ]
}
```

The daemon reloads this file automatically — no restart needed.

---

## Architecture

```
argon_daemon.py  (systemd root service)
    │
    ├── I2C bus 1, address 0x64  →  CW2217 battery chip
    │       register 0x04  →  battery percent
    │       register 0x0E  →  charge status (< 0x80 = charging)
    │       registers 0x10–0x59  →  76-byte battery profile (required for accurate SOC)
    │
    ├── I2C bus 14, address 0x37  →  DDC/CI display brightness (VCP 0x10)
    │
    ├── /sys/class/thermal/thermal_zone0/temp  →  CPU temperature
    ├── /sys/class/hwmon/hwmon3/fan1_input     →  fan RPM
    ├── /sys/class/hwmon/hwmon3/pwm1           →  fan PWM control
    ├── /sys/class/leds/default-on/brightness  →  keyboard backlight
    │
    ├── writes  →  /tmp/argon_dashboard_status   (JSON, every 2s)
    └── reads   ←  /tmp/argon_dashboard_control  (JSON, commands from UI)

argon_panel.sh      (XFCE Genmon plugin, reads status every 2s)
    └── click  →  argon_control.py  (GTK3 control panel)

argon_hotkeys.py    (systemd user service, evdev)
    └── Fn+F2 / KEY_BRIGHTNESSDOWN  →  brightness -10%
    └── Fn+F3 / KEY_BRIGHTNESSUP    →  brightness +10%
```

### IPC files

**`/tmp/argon_dashboard_status`** (written by daemon):
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

**`/tmp/argon_dashboard_control`** (written by UI/hotkeys, read by daemon):
```json
{
    "fan_mode": "auto",
    "fan_speed": 50,
    "kbd_backlight": true,
    "brightness": 80
}
```

---

## Troubleshooting

### Daemon not running
```bash
sudo systemctl status argon-dashboard
sudo journalctl -u argon-dashboard -f
```

### I2C errors
```bash
ls /dev/i2c-*
i2cdetect -y 1          # should show 0x64 (CW2217 battery)
i2cdetect -y 14         # should show 0x37 (DDC display)
i2cget -y 1 0x64 0x04   # battery percent
i2cget -y 1 0x64 0x0e   # charge status
```

### Panel applet not showing
```bash
sudo apt install xfce4-genmon-plugin
# Then add manually: right-click taskbar → Panel → Add Items → Generic Monitor
# Command: /usr/local/bin/argon_panel.sh  |  Interval: 2000ms
```

### Brightness not changing
```bash
# Check service permissions (DeviceAllow=/dev/i2c-14 must be present)
sudo systemctl cat argon-dashboard | grep DeviceAllow
# Restart service after any service file change:
sudo systemctl daemon-reload && sudo systemctl restart argon-dashboard
```

### Control panel won't open
```bash
python3 /usr/local/bin/argon_control.py
# Requires: python3-gi, gir1.2-gtk-3.0
sudo apt install python3-gi gir1.2-gtk-3.0
```

---

## File structure

```
argon-1-dashboard/
├── install.sh                    # Installation script
├── update.sh                     # Update script
├── uninstall.sh                  # Uninstall script
└── src/
    ├── argon_daemon.py           # Root daemon (I2C + DDC + fan + battery)
    ├── argon_panel.sh            # XFCE Genmon panel applet
    ├── argon_control.py          # GTK3 control panel (dark theme)
    ├── argon_hotkeys.py          # Fn key brightness hotkeys (user service)
    ├── argon-dashboard.service   # systemd root service
    ├── argonhotkeys.service      # systemd user service
    └── fan_config.json           # Default fan curve
```

---

## Tested on

- Raspberry Pi CM5 8GB / 32GB eMMC
- Argon ONE UP enclosure (v1)
- Kali Linux 2024.x XFCE (64-bit ARM)

---

## Contributing

Issues and pull requests are welcome.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m 'Add my feature'`
4. Push and open a pull request

---

## License

MIT — free to use and adapt.

---

## Keywords

`argon-one-up` `argon-one-up-cm5` `raspberry-pi-cm5` `raspberry-pi-laptop` `kali-linux` `xfce` `xfce-panel` `dashboard` `battery-monitor` `fan-control` `brightness-control` `ddc-ci` `cw2217` `i2c` `genmon` `gtk3` `systemd` `python3`
