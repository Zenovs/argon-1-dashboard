#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Argon ONE UP CM5 Dashboard Daemon

Liest Batterie-Status via I2C (Bus 1, Addr 0x64) und CPU-Temperatur.
Schreibt JSON-Status nach /tmp/argon_dashboard_status.

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
BATTERY_PERCENT_REG = 0x04
BATTERY_CHARGE_REG = 0x0E
CPU_TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
STATUS_FILE = "/tmp/argon_dashboard_status"
POLL_INTERVAL = 2  # Sekunden

# Globale Variable fuer sauberes Beenden
running = True
bus = None


def signal_handler(signum, frame):
    """Signal-Handler fuer sauberes Beenden (SIGTERM, SIGINT)."""
    global running
    print(f"Signal {signum} empfangen, beende Daemon...")
    running = False


def read_battery_percent():
    """Liest Batterie-Prozent von I2C Register 0x04."""
    try:
        value = bus.read_byte_data(BATTERY_ADDR, BATTERY_PERCENT_REG)
        # Wert auf 0-100 begrenzen
        return max(0, min(100, value))
    except Exception as e:
        print(f"WARNUNG: Batterie-Prozent konnte nicht gelesen werden: {e}", file=sys.stderr)
        return -1


def read_charging_status():
    """Liest Lade-Status von I2C Register 0x0E.
    
    Wert < 0x80 = laedt
    Wert >= 0x80 = entlaedt
    """
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
    # Status-Datei entfernen
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except Exception:
        pass
    print("Daemon sauber beendet.")


def main():
    global bus, running

    # Signal-Handler registrieren
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print("Argon Dashboard Daemon gestartet.")
    print(f"I2C Bus: {I2C_BUS}, Batterie-Adresse: {hex(BATTERY_ADDR)}")
    print(f"Status-Datei: {STATUS_FILE}")
    print(f"Poll-Intervall: {POLL_INTERVAL}s")

    # I2C-Bus oeffnen
    try:
        bus = smbus2.SMBus(I2C_BUS)
    except Exception as e:
        print(f"FEHLER: I2C-Bus {I2C_BUS} konnte nicht geoeffnet werden: {e}", file=sys.stderr)
        print("Ist I2C aktiviert? Pruefe mit: ls /dev/i2c-*", file=sys.stderr)
        sys.exit(1)

    try:
        while running:
            battery_percent = read_battery_percent()
            is_charging = read_charging_status()
            cpu_temp = read_cpu_temp()

            status = {
                "battery_percent": battery_percent,
                "is_charging": is_charging,
                "cpu_temp": cpu_temp,
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
