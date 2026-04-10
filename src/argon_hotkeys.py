#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Argon ONE UP CM5 - Hotkey Daemon (Benutzer-Service)

Hoert auf Fn+F2 (Helligkeit -) und Fn+F3 (Helligkeit +) und schreibt
Steuerbefehle in /tmp/argon_dashboard_control.

Autor: zenovs
Lizenz: MIT
"""

import json
import os
import sys
import time

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    print("FEHLER: evdev nicht installiert. Bitte 'pip3 install evdev' ausfuehren.", file=sys.stderr)
    sys.exit(1)

CONTROL_FILE = "/tmp/argon_dashboard_control"
STATUS_FILE = "/tmp/argon_dashboard_status"
BRIGHTNESS_STEP = 10
BRIGHTNESS_MIN = 10
BRIGHTNESS_MAX = 100


def read_current_brightness():
    """Liest aktuelle Helligkeit aus Status-Datei."""
    try:
        with open(STATUS_FILE) as f:
            return int(json.load(f).get("brightness", 80))
    except Exception:
        return 80


def write_brightness(value):
    """Schreibt Helligkeitsbefehl in Steuerdatei."""
    value = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, value))
    try:
        data = {}
        if os.path.exists(CONTROL_FILE):
            with open(CONTROL_FILE) as f:
                data = json.load(f)
    except Exception:
        data = {}
    data["brightness"] = value
    tmp = CONTROL_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, CONTROL_FILE)
    except Exception as e:
        print(f"FEHLER: Steuerdatei konnte nicht geschrieben werden: {e}", file=sys.stderr)


def find_keyboard():
    """Sucht Tastatur-InputDevice mit Helligkeits-Tasten."""
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            keys = caps.get(ecodes.EV_KEY, [])
            if (ecodes.KEY_BRIGHTNESSUP in keys or
                    ecodes.KEY_BRIGHTNESSDOWN in keys or
                    ecodes.KEY_F2 in keys):
                return dev
        except Exception:
            continue
    return None


def main():
    print("Argon Hotkey Daemon gestartet.")
    device = None

    while True:
        if device is None:
            device = find_keyboard()
            if device is None:
                time.sleep(5)
                continue
            print(f"Tastatur gefunden: {device.name} ({device.path})")

        try:
            for event in device.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                # Nur Tastendruck (value=1) und Halten (value=2)
                if event.value not in (1, 2):
                    continue

                if event.code in (ecodes.KEY_BRIGHTNESSUP, ecodes.KEY_F3):
                    brightness = read_current_brightness() + BRIGHTNESS_STEP
                    write_brightness(brightness)
                    print(f"Helligkeit +: {brightness}%")

                elif event.code in (ecodes.KEY_BRIGHTNESSDOWN, ecodes.KEY_F2):
                    brightness = read_current_brightness() - BRIGHTNESS_STEP
                    write_brightness(brightness)
                    print(f"Helligkeit -: {brightness}%")

        except OSError:
            print("Tastatur getrennt, suche neu...")
            device = None
            time.sleep(2)
        except Exception as e:
            print(f"Fehler: {e}", file=sys.stderr)
            time.sleep(1)


if __name__ == "__main__":
    main()
