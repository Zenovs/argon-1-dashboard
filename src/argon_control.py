#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Argon ONE UP CM5 Dashboard - GTK3 Control Panel

Zeigt Status und ermoeglicht Steuerung von:
- Luefter (Auto/Manuell + Slider)
- Tastaturbeleuchtung (Ein/Aus)

Autor: zenovs
Lizenz: MIT
"""

import json
import os
import sys

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib, Pango
except Exception:
    print("FEHLER: GTK3 nicht verfuegbar. Bitte installieren:", file=sys.stderr)
    print("  sudo apt install python3-gi gir1.2-gtk-3.0", file=sys.stderr)
    sys.exit(1)

STATUS_FILE = "/tmp/argon_dashboard_status"
CONTROL_FILE = "/tmp/argon_dashboard_control"


class ArgonControlWindow(Gtk.Window):
    """Hauptfenster des Argon Control Panels."""

    def __init__(self):
        super().__init__(title="Argon ONE UP CM5 - Steuerung")
        self.set_default_size(380, 420)
        self.set_resizable(False)
        self.set_border_width(12)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Aktueller Zustand
        self.fan_mode = "auto"
        self.fan_speed = 0
        self.kbd_backlight = False
        self._updating = False  # Verhindert Rueckkopplung

        # Initialen Zustand aus Control-Datei lesen
        self._load_control_state()

        # Layout erstellen
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # ── Titel ────────────────────────────────────────────
        title_label = Gtk.Label()
        title_label.set_markup("<b><big>🔧 Argon Dashboard Steuerung</big></b>")
        title_label.set_margin_bottom(5)
        main_box.pack_start(title_label, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(sep, False, False, 0)

        # ── Status-Anzeige ───────────────────────────────────
        status_frame = Gtk.Frame(label=" 📊 Status ")
        status_frame.set_margin_top(5)
        main_box.pack_start(status_frame, False, False, 0)

        status_grid = Gtk.Grid()
        status_grid.set_column_spacing(12)
        status_grid.set_row_spacing(6)
        status_grid.set_margin_top(8)
        status_grid.set_margin_bottom(8)
        status_grid.set_margin_start(10)
        status_grid.set_margin_end(10)
        status_frame.add(status_grid)

        # Status-Labels
        labels = ["🔋 Batterie:", "🌡 CPU-Temp:", "🌀 Luefter:"]
        self.status_values = []
        for i, text in enumerate(labels):
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.START)
            status_grid.attach(lbl, 0, i, 1, 1)

            val = Gtk.Label(label="--")
            val.set_halign(Gtk.Align.START)
            val.set_selectable(True)
            status_grid.attach(val, 1, i, 1, 1)
            self.status_values.append(val)

        # ── Lueftersteuerung ─────────────────────────────────
        fan_frame = Gtk.Frame(label=" 🌀 Lueftersteuerung ")
        fan_frame.set_margin_top(5)
        main_box.pack_start(fan_frame, False, False, 0)

        fan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fan_box.set_margin_top(8)
        fan_box.set_margin_bottom(8)
        fan_box.set_margin_start(10)
        fan_box.set_margin_end(10)
        fan_frame.add(fan_box)

        # Modus-Auswahl
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_label = Gtk.Label(label="Modus:")
        mode_box.pack_start(mode_label, False, False, 0)

        self.radio_auto = Gtk.RadioButton.new_with_label_from_widget(None, "Auto")
        self.radio_manual = Gtk.RadioButton.new_with_label_from_widget(self.radio_auto, "Manuell")
        mode_box.pack_start(self.radio_auto, False, False, 0)
        mode_box.pack_start(self.radio_manual, False, False, 0)

        if self.fan_mode == "manual":
            self.radio_manual.set_active(True)
        else:
            self.radio_auto.set_active(True)

        self.radio_auto.connect("toggled", self.on_fan_mode_changed)
        fan_box.pack_start(mode_box, False, False, 0)

        # Auto-Modus Info
        self.auto_info = Gtk.Label()
        self.auto_info.set_markup(
            "<small><i>Auto: &lt;50°C=0% | 50°C=30% | 60°C=50% | 65°C=75% | 70°C=100%</i></small>"
        )
        self.auto_info.set_line_wrap(True)
        self.auto_info.set_halign(Gtk.Align.START)
        fan_box.pack_start(self.auto_info, False, False, 0)

        # Slider
        slider_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        slider_label = Gtk.Label(label="Geschwindigkeit:")
        slider_box.pack_start(slider_label, False, False, 0)

        self.fan_adjustment = Gtk.Adjustment(
            value=self.fan_speed, lower=0, upper=100, step_increment=5, page_increment=10
        )
        self.fan_slider = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.fan_adjustment
        )
        self.fan_slider.set_digits(0)
        self.fan_slider.set_value_pos(Gtk.PositionType.RIGHT)
        self.fan_slider.set_hexpand(True)
        self.fan_slider.add_mark(0, Gtk.PositionType.BOTTOM, "0%")
        self.fan_slider.add_mark(50, Gtk.PositionType.BOTTOM, "50%")
        self.fan_slider.add_mark(100, Gtk.PositionType.BOTTOM, "100%")
        self.fan_slider.connect("value-changed", self.on_fan_speed_changed)
        slider_box.pack_start(self.fan_slider, True, True, 0)
        fan_box.pack_start(slider_box, False, False, 0)

        # Slider aktivieren/deaktivieren je nach Modus
        self.fan_slider.set_sensitive(self.fan_mode == "manual")

        # ── Tastaturbeleuchtung ──────────────────────────────
        kbd_frame = Gtk.Frame(label=" 💡 Tastaturbeleuchtung ")
        kbd_frame.set_margin_top(5)
        main_box.pack_start(kbd_frame, False, False, 0)

        kbd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        kbd_box.set_margin_top(8)
        kbd_box.set_margin_bottom(8)
        kbd_box.set_margin_start(10)
        kbd_box.set_margin_end(10)
        kbd_frame.add(kbd_box)

        kbd_label = Gtk.Label(label="Beleuchtung:")
        kbd_box.pack_start(kbd_label, False, False, 0)

        self.kbd_switch = Gtk.Switch()
        self.kbd_switch.set_active(self.kbd_backlight)
        self.kbd_switch.connect("notify::active", self.on_kbd_toggled)
        kbd_box.pack_start(self.kbd_switch, False, False, 0)

        self.kbd_status = Gtk.Label()
        self._update_kbd_label()
        kbd_box.pack_start(self.kbd_status, False, False, 0)

        # ── Schliessen-Button ────────────────────────────────
        close_btn = Gtk.Button(label="Schliessen")
        close_btn.set_margin_top(10)
        close_btn.connect("clicked", lambda w: self.destroy())
        main_box.pack_end(close_btn, False, False, 0)

        # Timer fuer Status-Updates (1 Sekunde)
        GLib.timeout_add_seconds(1, self.update_status)

        # Initialer Status
        self.update_status()

    def _load_control_state(self):
        """Laedt aktuellen Steuer-Zustand aus Control-Datei."""
        try:
            if os.path.exists(CONTROL_FILE):
                with open(CONTROL_FILE, "r") as f:
                    data = json.load(f)
                self.fan_mode = data.get("fan_mode", "auto")
                self.fan_speed = data.get("fan_speed", 0)
                self.kbd_backlight = data.get("kbd_backlight", False)
        except Exception:
            pass

    def _update_kbd_label(self):
        """Aktualisiert Tastaturbeleuchtungs-Label."""
        if self.kbd_switch.get_active():
            self.kbd_status.set_markup("<span foreground='#44CC44'><b>Ein</b></span>")
        else:
            self.kbd_status.set_markup("<span foreground='#888888'>Aus</span>")

    def on_fan_mode_changed(self, widget):
        """Handler fuer Lueftermodus-Aenderung."""
        if self._updating:
            return
        if self.radio_auto.get_active():
            self.fan_mode = "auto"
            self.fan_slider.set_sensitive(False)
        else:
            self.fan_mode = "manual"
            self.fan_slider.set_sensitive(True)
        self._write_control()

    def on_fan_speed_changed(self, widget):
        """Handler fuer Luefter-Slider-Aenderung."""
        if self._updating:
            return
        self.fan_speed = int(widget.get_value())
        self._write_control()

    def on_kbd_toggled(self, widget, gparam):
        """Handler fuer Tastaturbeleuchtungs-Toggle."""
        if self._updating:
            return
        self.kbd_backlight = widget.get_active()
        self._update_kbd_label()
        self._write_control()

    def _write_control(self):
        """Schreibt Steuerbefehle nach /tmp/argon_dashboard_control."""
        data = {
            "fan_mode": self.fan_mode,
            "fan_speed": self.fan_speed,
            "kbd_backlight": self.kbd_backlight
        }
        try:
            tmp_file = CONTROL_FILE + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump(data, f)
            os.replace(tmp_file, CONTROL_FILE)
        except Exception as e:
            print(f"FEHLER: Steuerdatei konnte nicht geschrieben werden: {e}", file=sys.stderr)

    def update_status(self):
        """Aktualisiert Status-Anzeige aus Status-Datei (Timer-Callback)."""
        try:
            if not os.path.exists(STATUS_FILE):
                for val in self.status_values:
                    val.set_markup("<span foreground='#888888'>Warte auf Daemon...</span>")
                return True

            with open(STATUS_FILE, "r") as f:
                data = json.load(f)

            # Batterie
            batt = data.get("battery_percent", -1)
            charging = data.get("is_charging")
            if batt == -1:
                batt_text = "--"
            else:
                charge_icon = "⚡" if charging else ""
                if batt < 20:
                    batt_text = f"<span foreground='#FF4444'><b>{batt}%</b></span> {charge_icon}"
                elif batt < 50:
                    batt_text = f"<span foreground='#FF8800'><b>{batt}%</b></span> {charge_icon}"
                else:
                    batt_text = f"<span foreground='#44CC44'><b>{batt}%</b></span> {charge_icon}"
                if charging:
                    batt_text += " (Laedt)"
            self.status_values[0].set_markup(batt_text)

            # Temperatur
            temp = data.get("cpu_temp", -1)
            if temp == -1:
                temp_text = "--"
            elif temp > 70:
                temp_text = f"<span foreground='#FF4444'><b>{temp}°C</b></span>"
            elif temp > 60:
                temp_text = f"<span foreground='#FF8800'><b>{temp}°C</b></span>"
            else:
                temp_text = f"<span foreground='#44CC44'><b>{temp}°C</b></span>"
            self.status_values[1].set_markup(temp_text)

            # Luefter
            fan_rpm = data.get("fan_rpm", -1)
            fan_speed = data.get("fan_speed", 0)
            fan_mode = data.get("fan_mode", "auto")
            mode_text = "Auto" if fan_mode == "auto" else "Manuell"
            if fan_rpm == -1:
                fan_text = f"-- ({mode_text})"
            else:
                fan_text = f"<b>{fan_rpm} RPM</b> ({fan_speed}%, {mode_text})"
            self.status_values[2].set_markup(fan_text)

            # UI-Zustand synchronisieren (ohne Rueckkopplung)
            self._updating = True
            if fan_mode == "auto" and not self.radio_auto.get_active():
                self.radio_auto.set_active(True)
                self.fan_slider.set_sensitive(False)
            elif fan_mode == "manual" and not self.radio_manual.get_active():
                self.radio_manual.set_active(True)
                self.fan_slider.set_sensitive(True)

            # Im Auto-Modus: Slider-Wert aus Status aktualisieren
            if fan_mode == "auto":
                self.fan_adjustment.set_value(fan_speed)

            # Tastaturbeleuchtung synchronisieren
            kbd = data.get("kbd_backlight", False)
            if kbd != self.kbd_switch.get_active():
                self.kbd_switch.set_active(kbd)
                self._update_kbd_label()
            self._updating = False

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Status-Update Fehler: {e}", file=sys.stderr)
            self._updating = False

        return True  # Timer weiterlaufen lassen


def main():
    # Pruefen ob bereits eine Instanz laeuft
    win = ArgonControlWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
