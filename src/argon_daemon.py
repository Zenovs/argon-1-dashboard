#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Argon ONE UP CM5 Dashboard Daemon

Liest Batterie-Status via I2C (Bus 1, Addr 0x64), CPU-Temperatur,
Luefter-RPM und steuert Luefter (PWM) sowie Tastaturbeleuchtung.
Schreibt JSON-Status nach /tmp/argon_dashboard_status.
Liest Steuerbefehle aus /tmp/argon_dashboard_control.

Autor: zenovs
Lizenz: MIT
"""

import json
import signal
import sys
import time
import os

try:
    import smbus2
except ImportError:
    print("FEHLER: smbus2 nicht installiert. Bitte 'pip3 install smbus2' ausfuehren.", file=sys.stderr)
    sys.exit(1)

# Konfiguration
I2C_BUS = 1
BATTERY_ADDR = 0x64
BATTERY_PERCENT_REG = 0x04   # CW2217: SOC Register (0-100%)
BATTERY_CHARGE_REG = 0x0E   # CW2217: < 0x80 = laedt, >= 0x80 = entlaedt
CW2217_MODE_REG = 0x08      # CW2217: Sleep/Mode Register
CPU_TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
STATUS_FILE = "/tmp/argon_dashboard_status"
CONTROL_FILE = "/tmp/argon_dashboard_control"
POLL_INTERVAL = 2  # Sekunden

# Luefter-Hardware-Pfade
FAN_RPM_PATH = "/sys/class/hwmon/hwmon3/fan1_input"
FAN_PWM_PATH = "/sys/class/hwmon/hwmon3/pwm1"
FAN_PWM_ENABLE_PATH = "/sys/class/hwmon/hwmon3/pwm1_enable"

# Tastaturbeleuchtung
KBD_BACKLIGHT_PATH = "/sys/class/leds/default-on/brightness"

# Luefter-Konfiguration
FAN_CONFIG_PATH = "/etc/argon/fan_config.json"

# Standard Luefter-Kurve (wird verwendet, falls Konfiguration fehlt)
DEFAULT_FAN_CURVE = [
    {"temp": 50, "speed": 0},
    {"temp": 55, "speed": 30},
    {"temp": 60, "speed": 50},
    {"temp": 65, "speed": 75},
    {"temp": 70, "speed": 100},
]

# Globale Variablen
running = True
bus = None
current_fan_mode = "auto"
current_fan_speed = 0  # Prozent (0-100)
current_kbd_backlight = False
fan_curve = list(DEFAULT_FAN_CURVE)  # Aktive Luefter-Kurve
fan_config_mtime = 0  # Letzte Aenderungszeit der Konfigurationsdatei
battery_history = []  # (timestamp, percent) fuer Zeitschätzung
HISTORY_SIZE = 1800  # 60 Minuten bei 2s Intervall


def signal_handler(signum, frame):
    """Signal-Handler fuer sauberes Beenden (SIGTERM, SIGINT)."""
    global running
    print(f"Signal {signum} empfangen, beende Daemon...")
    running = False


def init_cw2217():
    """Initialisiert CW2217 Chip (weckt aus Sleep-Modus)."""
    try:
        bus.write_byte_data(BATTERY_ADDR, CW2217_MODE_REG, 0x30)
        time.sleep(0.2)
        bus.write_byte_data(BATTERY_ADDR, CW2217_MODE_REG, 0x00)
        time.sleep(0.5)
        print("CW2217 Chip initialisiert.")
    except Exception as e:
        print(f"WARNUNG: CW2217 Initialisierung fehlgeschlagen: {e}", file=sys.stderr)


def read_battery_percent():
    """Liest Batterie-Prozent von CW2217 Register 0x04 (0-100%)."""
    try:
        value = bus.read_byte_data(BATTERY_ADDR, BATTERY_PERCENT_REG)
        return float(max(0, min(100, value)))
    except Exception as e:
        print(f"WARNUNG: Batterie-Prozent konnte nicht gelesen werden: {e}", file=sys.stderr)
        return -1.0


def read_charging_status():
    """Liest Lade-Status von CW2217 Register 0x0E (< 0x80 = laedt)."""
    try:
        value = bus.read_byte_data(BATTERY_ADDR, BATTERY_CHARGE_REG)
        return value < 0x80
    except Exception as e:
        print(f"WARNUNG: Lade-Status konnte nicht gelesen werden: {e}", file=sys.stderr)
        return None


def read_cpu_temp():
    """Liest CPU-Temperatur aus /sys/class/thermal/thermal_zone0/temp."""
    try:
        with open(CPU_TEMP_PATH, "r") as f:
            temp_raw = int(f.read().strip())
        return round(temp_raw / 1000.0, 1)
    except Exception as e:
        print(f"WARNUNG: CPU-Temperatur konnte nicht gelesen werden: {e}", file=sys.stderr)
        return -1.0


def read_fan_rpm():
    """Liest Luefter-RPM aus /sys/class/hwmon/hwmon3/fan1_input."""
    try:
        with open(FAN_RPM_PATH, "r") as f:
            return int(f.read().strip())
    except Exception as e:
        print(f"WARNUNG: Luefter-RPM konnte nicht gelesen werden: {e}", file=sys.stderr)
        return -1


def write_fan_pwm(pwm_value):
    """Schreibt PWM-Wert (0-255) nach /sys/class/hwmon/hwmon3/pwm1."""
    pwm_value = max(0, min(255, int(pwm_value)))
    try:
        # Sicherstellen dass PWM-Modus aktiv ist (1 = manuell)
        with open(FAN_PWM_ENABLE_PATH, "w") as f:
            f.write("1")
        with open(FAN_PWM_PATH, "w") as f:
            f.write(str(pwm_value))
    except PermissionError:
        print(f"FEHLER: Keine Berechtigung fuer {FAN_PWM_PATH}. Root-Rechte noetig!", file=sys.stderr)
    except Exception as e:
        print(f"WARNUNG: PWM konnte nicht geschrieben werden: {e}", file=sys.stderr)


def load_fan_config():
    """Laedt Luefter-Kurve aus /etc/argon/fan_config.json (bei Aenderung)."""
    global fan_curve, fan_config_mtime
    try:
        if not os.path.exists(FAN_CONFIG_PATH):
            fan_curve = list(DEFAULT_FAN_CURVE)
            fan_config_mtime = 0
            return

        mtime = os.path.getmtime(FAN_CONFIG_PATH)
        if mtime == fan_config_mtime:
            return  # Keine Aenderung

        with open(FAN_CONFIG_PATH, "r") as f:
            data = json.load(f)

        curve = data.get("fan_curve", [])
        if not curve or len(curve) < 2:
            print("WARNUNG: Ungueltige Luefter-Kurve, verwende Standard.", file=sys.stderr)
            fan_curve = list(DEFAULT_FAN_CURVE)
        else:
            # Validierung: aufsteigend sortiert nach Temperatur, Speed 0-100
            curve = sorted(curve, key=lambda p: p["temp"])
            valid = True
            for p in curve:
                if not (0 <= p.get("speed", -1) <= 100):
                    valid = False
                    break
            if valid:
                fan_curve = curve
                print(f"Luefter-Kurve geladen: {fan_curve}")
            else:
                print("WARNUNG: Ungueltige Werte in Luefter-Kurve, verwende Standard.", file=sys.stderr)
                fan_curve = list(DEFAULT_FAN_CURVE)

        fan_config_mtime = mtime

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"WARNUNG: Luefter-Konfiguration fehlerhaft: {e}", file=sys.stderr)
        fan_curve = list(DEFAULT_FAN_CURVE)
    except Exception as e:
        print(f"WARNUNG: Luefter-Konfiguration konnte nicht gelesen werden: {e}", file=sys.stderr)


def calculate_auto_fan(cpu_temp):
    """Berechnet Luefter-Prozent basierend auf CPU-Temperatur mit Interpolation."""
    if cpu_temp < 0:
        return 0, 0

    curve = fan_curve
    if not curve:
        return 0, 0

    # Unterhalb des ersten Punktes: Speed des ersten Punktes
    if cpu_temp <= curve[0]["temp"]:
        speed = curve[0]["speed"]
        pwm = int(speed * 255 / 100)
        return pwm, speed

    # Oberhalb des letzten Punktes: Speed des letzten Punktes
    if cpu_temp >= curve[-1]["temp"]:
        speed = curve[-1]["speed"]
        pwm = int(speed * 255 / 100)
        return pwm, speed

    # Interpolation zwischen Punkten
    for i in range(len(curve) - 1):
        t1, s1 = curve[i]["temp"], curve[i]["speed"]
        t2, s2 = curve[i + 1]["temp"], curve[i + 1]["speed"]
        if t1 <= cpu_temp <= t2:
            if t2 == t1:
                speed = s2
            else:
                # Lineare Interpolation
                ratio = (cpu_temp - t1) / (t2 - t1)
                speed = s1 + ratio * (s2 - s1)
            speed = int(round(speed))
            speed = max(0, min(100, speed))
            pwm = int(speed * 255 / 100)
            return pwm, speed

    return 0, 0


def estimate_battery_time(current_pct):
    """Schaetzt verbleibende Lade/Entladezeit in Minuten.
    Gibt (rate_%/h, time_min_or_None, stable_bool) zurueck."""
    if len(battery_history) < 30 or current_pct < 0:
        return 0.0, None, False

    t1, p1 = battery_history[0]
    t2, p2 = battery_history[-1]
    dt_hours = (t2 - t1) / 3600.0

    if dt_hours < 0.005:
        return 0.0, None, False

    rate = (p2 - p1) / dt_hours  # %/Stunde, positiv=laedt, negativ=entlaedt

    if abs(rate) < 0.1:
        return 0.0, None, True  # Genuegend Daten, aber stabil

    if rate < 0 and current_pct > 0:
        return rate, (current_pct / abs(rate)) * 60, False
    elif rate > 0 and current_pct < 100:
        return rate, ((100 - current_pct) / rate) * 60, False

    return rate, None, False


def write_kbd_backlight(on):
    """Setzt Tastaturbeleuchtung (0=aus, 1=ein)."""
    try:
        with open(KBD_BACKLIGHT_PATH, "w") as f:
            f.write("1" if on else "0")
    except PermissionError:
        print(f"FEHLER: Keine Berechtigung fuer {KBD_BACKLIGHT_PATH}. Root-Rechte noetig!", file=sys.stderr)
    except Exception as e:
        print(f"WARNUNG: Tastaturbeleuchtung konnte nicht gesetzt werden: {e}", file=sys.stderr)


def read_kbd_backlight():
    """Liest aktuellen Zustand der Tastaturbeleuchtung."""
    try:
        with open(KBD_BACKLIGHT_PATH, "r") as f:
            return int(f.read().strip()) > 0
    except Exception:
        return False


def read_control_commands():
    """Liest Steuerbefehle aus /tmp/argon_dashboard_control."""
    global current_fan_mode, current_fan_speed, current_kbd_backlight
    try:
        if os.path.exists(CONTROL_FILE):
            with open(CONTROL_FILE, "r") as f:
                data = json.load(f)

            if "fan_mode" in data:
                mode = data["fan_mode"]
                if mode in ("auto", "manual"):
                    current_fan_mode = mode

            if "fan_speed" in data:
                speed = int(data["fan_speed"])
                current_fan_speed = max(0, min(100, speed))

            if "kbd_backlight" in data:
                new_state = bool(data["kbd_backlight"])
                if new_state != current_kbd_backlight:
                    current_kbd_backlight = new_state
                    write_kbd_backlight(current_kbd_backlight)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"WARNUNG: Steuerdatei konnte nicht gelesen werden: {e}", file=sys.stderr)


def write_status(data):
    """Schreibt Status-JSON atomar nach /tmp/argon_dashboard_status."""
    tmp_file = STATUS_FILE + ".tmp"
    try:
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, STATUS_FILE)
    except Exception as e:
        print(f"FEHLER: Status konnte nicht geschrieben werden: {e}", file=sys.stderr)


def cleanup():
    """Aufraeumen beim Beenden."""
    global bus
    if bus is not None:
        try:
            bus.close()
        except Exception:
            pass
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except Exception:
        pass
    print("Daemon sauber beendet.")


def main():
    global bus, running, current_fan_mode, current_fan_speed, current_kbd_backlight

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print("Argon Dashboard Daemon gestartet.")
    print(f"I2C Bus: {I2C_BUS}, Batterie-Adresse: {hex(BATTERY_ADDR)}")
    print(f"Luefter PWM: {FAN_PWM_PATH}")
    print(f"Tastaturbeleuchtung: {KBD_BACKLIGHT_PATH}")
    print(f"Status-Datei: {STATUS_FILE}")
    print(f"Steuer-Datei: {CONTROL_FILE}")
    print(f"Poll-Intervall: {POLL_INTERVAL}s")

    # I2C-Bus oeffnen
    try:
        bus = smbus2.SMBus(I2C_BUS)
    except Exception as e:
        print(f"FEHLER: I2C-Bus {I2C_BUS} konnte nicht geoeffnet werden: {e}", file=sys.stderr)
        print("Ist I2C aktiviert? Pruefe mit: ls /dev/i2c-*", file=sys.stderr)
        sys.exit(1)

    # CW2217 Chip initialisieren (aus Sleep-Modus wecken)
    init_cw2217()

    # Initialen Zustand der Tastaturbeleuchtung lesen
    current_kbd_backlight = read_kbd_backlight()

    # Luefter-Konfiguration laden
    load_fan_config()

    try:
        while running:
            # Luefter-Konfiguration bei Aenderung neu laden
            load_fan_config()

            # Steuerbefehle lesen
            read_control_commands()

            # Sensordaten lesen
            battery_percent = read_battery_percent()
            is_charging = read_charging_status()
            cpu_temp = read_cpu_temp()
            fan_rpm = read_fan_rpm()

            # Akkuverlauf aktualisieren
            if battery_percent >= 0:
                battery_history.append((time.time(), battery_percent))
                if len(battery_history) > HISTORY_SIZE:
                    battery_history.pop(0)

            battery_rate, time_remaining, battery_stable = estimate_battery_time(battery_percent)

            # Lueftersteuerung
            if current_fan_mode == "auto":
                pwm_value, fan_percent = calculate_auto_fan(cpu_temp)
                write_fan_pwm(pwm_value)
                current_fan_speed = fan_percent
            else:
                # Manueller Modus: Prozent -> PWM (0-100% -> 0-255)
                pwm_value = int(current_fan_speed * 255 / 100)
                write_fan_pwm(pwm_value)

            status = {
                "battery_percent": battery_percent,
                "is_charging": is_charging,
                "battery_rate": battery_rate,
                "time_remaining": time_remaining,
                "cpu_temp": cpu_temp,
                "fan_rpm": fan_rpm,
                "fan_speed": current_fan_speed,
                "fan_mode": current_fan_mode,
                "kbd_backlight": current_kbd_backlight,
                "timestamp": time.time()
            }

            write_status(status)
            time.sleep(POLL_INTERVAL)
    except Exception as e:
        print(f"FEHLER im Hauptloop: {e}", file=sys.stderr)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
