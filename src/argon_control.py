#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Argon ONE UP CM5 Dashboard - GTK3 Control Panel

Zeigt Status und ermoeglicht Steuerung von:
- Luefter (Auto/Manuell + Slider)
- Luefter-Kurve (konfigurierbar)
- Tastaturbeleuchtung (Ein/Aus)

Autor: zenovs
Lizenz: MIT
"""

import fcntl
import html
import json
import os
import shutil
import subprocess
import sys
import time

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib
except Exception:
    print("FEHLER: GTK3 nicht verfuegbar. Bitte installieren:", file=sys.stderr)
    print("  sudo apt install python3-gi gir1.2-gtk-3.0", file=sys.stderr)
    sys.exit(1)

STATUS_FILE = "/tmp/argon_dashboard_status"
CONTROL_FILE = "/tmp/argon_dashboard_control"
FAN_CONFIG_PATH = "/etc/argon/fan_config.json"
LID_CONFIG_PATH = "/etc/systemd/logind.conf.d/argon-lid.conf"
LOGIND_CONF_PATH = "/etc/systemd/logind.conf"
LOCK_HOOK_PATH = "/usr/lib/systemd/system-sleep/argon-lock-screen"
LOCK_HOOK_CONTENT = """\
#!/bin/bash
# Argon Dashboard - Bildschirm vor Standby sperren
[ "$1" = "pre" ] || exit 0

# Alle aktiven graphischen Sessions sperren
for session in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}'); do
    session_type=$(loginctl show-session "$session" -p Type --value 2>/dev/null)
    if [ "$session_type" = "x11" ] || [ "$session_type" = "wayland" ]; then
        loginctl lock-session "$session" 2>/dev/null
    fi
done

sleep 1
"""

LID_ACTIONS = [
    ("suspend",      "Standby (Suspend)"),
    ("hibernate",    "Ruhezustand (Hibernate)"),
    ("hybrid-sleep", "Hybrid-Schlaf"),
    ("lock",         "Bildschirm sperren"),
    ("ignore",       "Nichts tun"),
    ("poweroff",     "Ausschalten"),
]

DEFAULT_FAN_CURVE = [
    {"temp": 50, "speed": 0},
    {"temp": 55, "speed": 30},
    {"temp": 60, "speed": 50},
    {"temp": 65, "speed": 75},
    {"temp": 70, "speed": 100},
]


class ArgonControlWindow(Gtk.Window):
    """Hauptfenster des Argon Control Panels."""

    CSS = b"""
    window {
        background-color: #1e1e2e;
    }
    frame {
        color: #a6adc8;
    }
    frame > border {
        border-color: #313244;
        border-radius: 8px;
    }
    label {
        color: #cdd6f4;
    }
    .title-label {
        color: #cdd6f4;
        font-size: 15px;
        font-weight: bold;
    }
    .section-label {
        color: #89b4fa;
        font-weight: bold;
    }
    .dim-label {
        color: #6c7086;
        font-size: 11px;
    }
    button {
        background: #313244;
        background-image: none;
        border: 1px solid #45475a;
        border-radius: 6px;
        color: #cdd6f4;
        padding: 4px 10px;
        box-shadow: none;
    }
    button:hover {
        background: #45475a;
        background-image: none;
    }
    button:active {
        background: #585b70;
        background-image: none;
    }
    scale trough {
        background-color: #313244;
        border-radius: 4px;
        min-height: 4px;
    }
    scale highlight {
        background-color: #89b4fa;
        border-radius: 4px;
    }
    scale slider {
        background-color: #cdd6f4;
        border-radius: 50%;
        min-width: 16px;
        min-height: 16px;
        border: none;
        box-shadow: none;
        -gtk-outline-radius: 50%;
    }
    scale marks indicator {
        background-color: transparent;
        min-width: 0;
        min-height: 0;
    }
    scale mark label {
        color: #6c7086;
        font-size: 10px;
    }
    image {
        color: #cdd6f4;
        -gtk-icon-style: symbolic;
    }
    .status-value {
        color: #cdd6f4;
    }
    spinbutton {
        background-color: #313244;
        color: #cdd6f4;
        border-color: #45475a;
        border-radius: 4px;
    }
    spinbutton text {
        color: #cdd6f4;
    }
    radiobutton label, checkbutton label {
        color: #cdd6f4;
    }
    combobox button {
        background-color: #313244;
        color: #cdd6f4;
        border-color: #45475a;
    }
    separator {
        background-color: #313244;
    }
    """

    def _apply_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(self.CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    @staticmethod
    def _icon(name, size=Gtk.IconSize.SMALL_TOOLBAR):
        img = Gtk.Image.new_from_icon_name(name, size)
        return img

    @staticmethod
    def _section(icon_name, text):
        """Erstellt ein Icon+Label fuer Frame-Bereiche."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR), False, False, 0)
        lbl = Gtk.Label(label=f" {text} ")
        lbl.get_style_context().add_class("section-label")
        box.pack_start(lbl, False, False, 0)
        return box

    def __init__(self):
        super().__init__(title="Argon ONE UP — Dashboard")
        self.set_default_size(440, 760)
        self.set_resizable(False)
        self.set_border_width(14)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Aktueller Zustand
        self.fan_mode = "auto"
        self.fan_speed = 0
        self.kbd_backlight = False
        self._updating = False
        self._bright_changed_at = 0  # Zeitstempel der letzten Nutzer-Aenderung

        # Aktuelle Helligkeit aus Status-Datei lesen (vor Slider-Erstellung)
        self._initial_brightness = 80
        try:
            with open(STATUS_FILE) as f:
                self._initial_brightness = int(json.load(f).get("brightness", 80))
        except Exception:
            pass

        self._load_control_state()

        # CSS anwenden
        self._apply_css()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # ── Titel ────────────────────────────────────────────
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_margin_bottom(4)
        title_icon = Gtk.Image.new_from_icon_name("computer-laptop-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        title_box.pack_start(title_icon, False, False, 0)
        title_lbl = Gtk.Label(label="Argon ONE UP  —  Dashboard")
        title_lbl.get_style_context().add_class("title-label")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.pack_start(title_lbl, False, False, 0)
        main_box.pack_start(title_box, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(sep, False, False, 0)

        # ── Status-Anzeige ───────────────────────────────────
        status_frame = Gtk.Frame()
        status_frame.set_label_widget(self._section("dialog-information-symbolic", "Status"))
        status_frame.set_margin_top(4)
        main_box.pack_start(status_frame, False, False, 0)

        status_grid = Gtk.Grid()
        status_grid.set_column_spacing(14)
        status_grid.set_row_spacing(7)
        status_grid.set_margin_top(10)
        status_grid.set_margin_bottom(10)
        status_grid.set_margin_start(12)
        status_grid.set_margin_end(12)
        status_frame.add(status_grid)

        icon_labels = [
            ("battery-good-symbolic",          "Batterie"),
            ("temperature-symbolic",           "CPU-Temp"),
            ("system-run-symbolic",            "Luefter"),
            ("battery-full-charging-symbolic", "Ladestatus"),
            ("alarm-symbolic",                 "Restzeit"),
        ]
        self.status_values = []
        for i, (icon_name, text) in enumerate(icon_labels):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR), False, False, 0)
            lbl = Gtk.Label(label=text + ":")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_size_request(110, -1)
            row.pack_start(lbl, False, False, 0)
            status_grid.attach(row, 0, i, 1, 1)

            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.START)
            val.set_selectable(True)
            status_grid.attach(val, 1, i, 1, 1)
            self.status_values.append(val)

        # ── Helligkeit ───────────────────────────────────────
        bright_frame = Gtk.Frame()
        bright_frame.set_label_widget(self._section("display-brightness-symbolic", "Bildschirmhelligkeit"))
        bright_frame.set_margin_top(6)
        main_box.pack_start(bright_frame, False, False, 0)

        bright_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bright_outer.set_margin_top(8)
        bright_outer.set_margin_bottom(8)
        bright_outer.set_margin_start(12)
        bright_outer.set_margin_end(12)
        bright_frame.add(bright_outer)

        bright_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bright_outer.pack_start(bright_box, False, False, 0)

        bright_box.pack_start(self._icon("weather-clear-night-symbolic"), False, False, 0)

        self.bright_adjustment = Gtk.Adjustment(
            value=self._initial_brightness, lower=10, upper=100, step_increment=5, page_increment=10
        )
        self.bright_slider = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.bright_adjustment
        )
        self.bright_slider.set_digits(0)
        self.bright_slider.set_draw_value(False)
        self.bright_slider.set_hexpand(True)
        self.bright_slider.connect("value-changed", self.on_brightness_changed)
        bright_box.pack_start(self.bright_slider, True, True, 0)
        bright_box.pack_start(self._icon("weather-clear-symbolic"), False, False, 0)

        self.bright_label = Gtk.Label(label=f"{self._initial_brightness}%")
        self.bright_label.set_halign(Gtk.Align.CENTER)
        self.bright_label.get_style_context().add_class("dim-label")
        bright_outer.pack_start(self.bright_label, False, False, 0)

        # ── Lueftersteuerung ─────────────────────────────────
        fan_frame = Gtk.Frame()
        fan_frame.set_label_widget(self._section("system-run-symbolic", "Lueftersteuerung"))
        fan_frame.set_margin_top(6)
        main_box.pack_start(fan_frame, False, False, 0)

        fan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fan_box.set_margin_top(10)
        fan_box.set_margin_bottom(10)
        fan_box.set_margin_start(12)
        fan_box.set_margin_end(12)
        fan_frame.add(fan_box)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_lbl = Gtk.Label(label="Modus:")
        mode_box.pack_start(mode_lbl, False, False, 0)
        self.radio_auto = Gtk.RadioButton.new_with_label_from_widget(None, "Auto")
        self.radio_manual = Gtk.RadioButton.new_with_label_from_widget(self.radio_auto, "Manuell")
        mode_box.pack_start(self.radio_auto, False, False, 0)
        mode_box.pack_start(self.radio_manual, False, False, 0)
        if self.fan_mode == "manual":
            self.radio_manual.set_active(True)
        self.radio_auto.connect("toggled", self.on_fan_mode_changed)
        fan_box.pack_start(mode_box, False, False, 0)

        self.auto_info = Gtk.Label()
        self.auto_info.get_style_context().add_class("dim-label")
        self._update_auto_info_label()
        self.auto_info.set_line_wrap(True)
        self.auto_info.set_halign(Gtk.Align.START)
        fan_box.pack_start(self.auto_info, False, False, 0)

        slider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        fan_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fan_row.pack_start(Gtk.Label(label="Geschwindigkeit:"), False, False, 0)
        self.fan_adjustment = Gtk.Adjustment(
            value=self.fan_speed, lower=0, upper=100, step_increment=5, page_increment=10
        )
        self.fan_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.fan_adjustment)
        self.fan_slider.set_digits(0)
        self.fan_slider.set_draw_value(False)
        self.fan_slider.set_hexpand(True)
        self.fan_slider.connect("value-changed", self.on_fan_speed_changed)
        fan_row.pack_start(self.fan_slider, True, True, 0)
        self.fan_speed_label = Gtk.Label(label=f"{self.fan_speed}%")
        self.fan_speed_label.set_width_chars(4)
        self.fan_speed_label.get_style_context().add_class("dim-label")
        fan_row.pack_start(self.fan_speed_label, False, False, 0)
        slider_box.pack_start(fan_row, False, False, 0)
        fan_box.pack_start(slider_box, False, False, 0)
        self.fan_slider.set_sensitive(self.fan_mode == "manual")

        # ── Luefter-Kurve ─────────────────────────────────────
        curve_frame = Gtk.Frame()
        curve_frame.set_label_widget(self._section("preferences-system-symbolic", "Luefter-Kurve"))
        curve_frame.set_margin_top(6)
        main_box.pack_start(curve_frame, False, False, 0)

        curve_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        curve_box.set_margin_top(10)
        curve_box.set_margin_bottom(10)
        curve_box.set_margin_start(12)
        curve_box.set_margin_end(12)
        curve_frame.add(curve_box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        th = Gtk.Label()
        th.set_markup("<b>Temperatur (°C)</b>")
        th.set_size_request(140, -1)
        header_box.pack_start(th, False, False, 0)
        header_box.pack_start(Gtk.Label(label="→"), False, False, 0)
        sh = Gtk.Label()
        sh.set_markup("<b>Luefter (%)</b>")
        sh.set_size_request(140, -1)
        header_box.pack_start(sh, False, False, 0)
        curve_box.pack_start(header_box, False, False, 0)

        self.curve_entries = []
        current_curve = self._load_fan_curve()
        for i in range(5):
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            temp_adj = Gtk.Adjustment(value=current_curve[i]["temp"] if i < len(current_curve) else 50 + i * 5,
                                      lower=0, upper=100, step_increment=1, page_increment=5)
            temp_spin = Gtk.SpinButton(adjustment=temp_adj, climb_rate=1, digits=0)
            temp_spin.set_size_request(140, -1)
            row_box.pack_start(temp_spin, False, False, 0)
            row_box.pack_start(Gtk.Label(label="→"), False, False, 0)
            speed_adj = Gtk.Adjustment(value=current_curve[i]["speed"] if i < len(current_curve) else 0,
                                       lower=0, upper=100, step_increment=1, page_increment=5)
            speed_spin = Gtk.SpinButton(adjustment=speed_adj, climb_rate=1, digits=0)
            speed_spin.set_size_request(140, -1)
            row_box.pack_start(speed_spin, False, False, 0)
            curve_box.pack_start(row_box, False, False, 0)
            self.curve_entries.append((temp_spin, speed_spin))

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(4)
        save_btn = Gtk.Button()
        save_btn.set_image(Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON))
        save_btn.set_label("Speichern")
        save_btn.set_always_show_image(True)
        save_btn.connect("clicked", self.on_save_curve)
        btn_box.pack_start(save_btn, True, True, 0)
        reset_btn = Gtk.Button()
        reset_btn.set_image(Gtk.Image.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.BUTTON))
        reset_btn.set_label("Standard")
        reset_btn.set_always_show_image(True)
        reset_btn.connect("clicked", self.on_reset_curve)
        btn_box.pack_start(reset_btn, True, True, 0)
        curve_box.pack_start(btn_box, False, False, 0)

        self.curve_status = Gtk.Label()
        self.curve_status.set_halign(Gtk.Align.START)
        curve_box.pack_start(self.curve_status, False, False, 0)

        # ── Deckel-Aktion ────────────────────────────────────
        lid_frame = Gtk.Frame()
        lid_frame.set_label_widget(self._section("system-suspend-symbolic", "Deckel zuklappen"))
        lid_frame.set_margin_top(6)
        main_box.pack_start(lid_frame, False, False, 0)

        lid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lid_box.set_margin_top(10)
        lid_box.set_margin_bottom(10)
        lid_box.set_margin_start(12)
        lid_box.set_margin_end(12)
        lid_frame.add(lid_box)

        lid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lid_row.pack_start(Gtk.Label(label="Aktion:"), False, False, 0)
        self.lid_combo = Gtk.ComboBoxText()
        for _, label in LID_ACTIONS:
            self.lid_combo.append_text(label)
        current_action = self._read_lid_action()
        action_keys = [a[0] for a in LID_ACTIONS]
        self.lid_combo.set_active(action_keys.index(current_action) if current_action in action_keys else 0)
        lid_row.pack_start(self.lid_combo, True, True, 0)
        lid_apply_btn = Gtk.Button()
        lid_apply_btn.set_image(Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.BUTTON))
        lid_apply_btn.set_label("Anwenden")
        lid_apply_btn.set_always_show_image(True)
        lid_apply_btn.connect("clicked", self.on_save_lid_action)
        lid_row.pack_start(lid_apply_btn, False, False, 0)
        lid_box.pack_start(lid_row, False, False, 0)

        self.lid_status = Gtk.Label()
        self.lid_status.set_halign(Gtk.Align.START)
        lid_box.pack_start(self.lid_status, False, False, 0)

        lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lock_row.pack_start(Gtk.Image.new_from_icon_name("system-lock-screen-symbolic", Gtk.IconSize.SMALL_TOOLBAR), False, False, 0)
        self.lock_check = Gtk.CheckButton(label="Passwort beim Aufwachen verlangen")
        self.lock_check.set_active(self._read_lock_on_resume())
        self.lock_check.connect("toggled", self.on_lock_on_resume_toggled)
        lock_row.pack_start(self.lock_check, False, False, 0)
        lid_box.pack_start(lock_row, False, False, 0)

        self.lock_status = Gtk.Label()
        self.lock_status.set_halign(Gtk.Align.START)
        lid_box.pack_start(self.lock_status, False, False, 0)

        # ── Buttons unten ────────────────────────────────────
        btn_bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_bottom.set_margin_top(10)

        update_btn = Gtk.Button()
        update_btn.set_image(Gtk.Image.new_from_icon_name("software-update-available-symbolic", Gtk.IconSize.BUTTON))
        update_btn.set_label("Update")
        update_btn.set_always_show_image(True)
        update_btn.connect("clicked", self.on_update_clicked)
        btn_bottom.pack_start(update_btn, True, True, 0)

        close_btn = Gtk.Button()
        close_btn.set_image(Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON))
        close_btn.set_label("Schliessen")
        close_btn.set_always_show_image(True)
        close_btn.connect("clicked", lambda w: self.destroy())
        btn_bottom.pack_start(close_btn, True, True, 0)

        main_box.pack_end(btn_bottom, False, False, 0)

        GLib.timeout_add_seconds(1, self.update_status)
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

    def _load_fan_curve(self):
        """Laedt aktuelle Luefter-Kurve aus Konfigurationsdatei."""
        try:
            if os.path.exists(FAN_CONFIG_PATH):
                with open(FAN_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                curve = data.get("fan_curve", DEFAULT_FAN_CURVE)
                if curve and len(curve) >= 2:
                    return curve
        except Exception:
            pass
        return list(DEFAULT_FAN_CURVE)

    def _update_auto_info_label(self):
        """Aktualisiert das Auto-Modus Info-Label basierend auf der aktuellen Kurve."""
        curve = self._load_fan_curve()
        parts = []
        for p in curve:
            parts.append(f"{p['temp']}°C={p['speed']}%")
        info_text = " | ".join(parts)
        self.auto_info.set_markup(f"<small><i>Auto: {info_text}</i></small>")

    def _update_kbd_label(self):
        """Aktualisiert Tastaturbeleuchtungs-Label (falls Widget vorhanden)."""
        if not hasattr(self, "kbd_switch") or not hasattr(self, "kbd_status"):
            return
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

    def on_brightness_changed(self, widget):
        """Handler fuer Helligkeits-Slider-Aenderung."""
        val = int(self.bright_adjustment.get_value())
        self.bright_label.set_text(f"{val}%")
        if self._updating:
            return
        self._bright_changed_at = time.time()
        self._write_control()

    def on_fan_speed_changed(self, widget):
        """Handler fuer Luefter-Slider-Aenderung."""
        val = int(widget.get_value())
        self.fan_speed_label.set_text(f"{val}%")
        if self._updating:
            return
        self.fan_speed = val
        self._write_control()

    def on_kbd_toggled(self, widget, gparam):
        """Handler fuer Tastaturbeleuchtungs-Toggle."""
        if self._updating:
            return
        self.kbd_backlight = widget.get_active()
        self._update_kbd_label()
        self._write_control()

    def on_save_curve(self, widget):
        """Speichert Luefter-Kurve nach /etc/argon/fan_config.json (via sudo)."""
        # Werte auslesen
        curve = []
        for temp_spin, speed_spin in self.curve_entries:
            temp = int(temp_spin.get_value())
            speed = int(speed_spin.get_value())
            curve.append({"temp": temp, "speed": speed})

        # Validierung: Temperatur muss aufsteigend sein
        for i in range(1, len(curve)):
            if curve[i]["temp"] <= curve[i - 1]["temp"]:
                self.curve_status.set_markup(
                    "<span foreground='#FF4444'>❌ Fehler: Temperaturen muessen aufsteigend sein!</span>"
                )
                return

        # Validierung: Speed 0-100
        for p in curve:
            if not (0 <= p["speed"] <= 100):
                self.curve_status.set_markup(
                    "<span foreground='#FF4444'>❌ Fehler: Luefter-Geschwindigkeit muss 0-100% sein!</span>"
                )
                return

        # JSON erstellen
        config_data = json.dumps({"fan_curve": curve}, indent=4)

        # Mit pkexec/sudo schreiben
        try:
            # Versuche direkt zu schreiben (falls Rechte vorhanden)
            os.makedirs("/etc/argon", exist_ok=True)
            with open(FAN_CONFIG_PATH, "w") as f:
                f.write(config_data + "\n")
            self.curve_status.set_markup(
                "<span foreground='#44CC44'>✅ Luefter-Kurve gespeichert! Daemon uebernimmt automatisch.</span>"
            )
            self._update_auto_info_label()
        except PermissionError:
            # Fallback: Mit pkexec schreiben (kein bash -c, kein Injection-Risiko)
            try:
                result = subprocess.run(
                    ["pkexec", "tee", FAN_CONFIG_PATH],
                    input=(config_data + "\n").encode(),
                    capture_output=True, timeout=30
                )
                if result.returncode == 0:
                    self.curve_status.set_markup(
                        "<span foreground='#44CC44'>✅ Luefter-Kurve gespeichert! Daemon uebernimmt automatisch.</span>"
                    )
                    self._update_auto_info_label()
                else:
                    self.curve_status.set_markup(
                        "<span foreground='#FF4444'>❌ Fehler: Keine Root-Rechte erhalten.</span>"
                    )
            except subprocess.TimeoutExpired:
                self.curve_status.set_markup(
                    "<span foreground='#FF4444'>❌ Fehler: Zeitueberschreitung bei Authentifizierung.</span>"
                )
            except Exception as e:
                self.curve_status.set_markup(
                    f"<span foreground='#FF4444'>❌ Fehler: {html.escape(str(e))}</span>"
                )
        except Exception as e:
            self.curve_status.set_markup(
                f"<span foreground='#FF4444'>❌ Fehler: {html.escape(str(e))}</span>"
            )

    def on_reset_curve(self, widget):
        """Setzt Luefter-Kurve auf Standard zurueck."""
        for i, (temp_spin, speed_spin) in enumerate(self.curve_entries):
            if i < len(DEFAULT_FAN_CURVE):
                temp_spin.set_value(DEFAULT_FAN_CURVE[i]["temp"])
                speed_spin.set_value(DEFAULT_FAN_CURVE[i]["speed"])

        self.curve_status.set_markup(
            "<span foreground='#FF8800'>🔄 Standard wiederhergestellt. Klicke 'Speichern' zum Uebernehmen.</span>"
        )

    def on_update_clicked(self, widget):
        """Oeffnet Terminal und fuehrt Update-Skript aus."""
        update_cmd = (
            "curl -fsSL https://raw.githubusercontent.com/Zenovs/argon-1-dashboard/main/update.sh"
            " | sudo bash"
            "; echo ''; echo 'Druecke ENTER zum Schliessen...'; read"
        )
        for terminal in ["xfce4-terminal", "x-terminal-emulator", "xterm"]:
            try:
                subprocess.Popen([terminal, "-e", "bash", "-c", update_cmd])
                return
            except FileNotFoundError:
                continue

    def _read_lid_action(self):
        """Liest aktuelle Deckel-Aktion aus logind-Konfiguration."""
        for path in [LID_CONFIG_PATH, LOGIND_CONF_PATH]:
            try:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("HandleLidSwitch=") and not line.startswith("#"):
                                return line.split("=", 1)[1].strip()
            except Exception:
                pass
        return "suspend"

    def on_save_lid_action(self, widget):
        """Speichert Deckel-Aktion nach /etc/systemd/logind.conf.d/argon-lid.conf."""
        idx = self.lid_combo.get_active()
        if idx < 0:
            return
        action = LID_ACTIONS[idx][0]

        try:
            os.makedirs("/etc/systemd/logind.conf.d", exist_ok=True)
            with open(LID_CONFIG_PATH, "w") as f:
                f.write(f"[Login]\nHandleLidSwitch={action}\n")
            subprocess.run(["systemctl", "reload", "systemd-logind"],
                           capture_output=True, timeout=10)
            self.lid_status.set_markup(
                "<span foreground='#44CC44'>✅ Gespeichert! Aktiv ab naechstem Deckel-Zuklappen.</span>"
            )
        except PermissionError:
            try:
                bash_cmd = (
                    f"mkdir -p /etc/systemd/logind.conf.d && "
                    f"printf '[Login]\\nHandleLidSwitch={action}\\n' "
                    f"> {LID_CONFIG_PATH} && "
                    f"chmod 644 {LID_CONFIG_PATH} && "
                    f"systemctl reload systemd-logind"
                )
                result = subprocess.run(
                    ["pkexec", "bash", "-c", bash_cmd],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    self.lid_status.set_markup(
                        "<span foreground='#44CC44'>✅ Gespeichert! Aktiv ab naechstem Deckel-Zuklappen.</span>"
                    )
                else:
                    self.lid_status.set_markup(
                        "<span foreground='#FF4444'>❌ Fehler: Keine Root-Rechte erhalten.</span>"
                    )
            except subprocess.TimeoutExpired:
                self.lid_status.set_markup(
                    "<span foreground='#FF4444'>❌ Fehler: Zeitueberschreitung bei Authentifizierung.</span>"
                )
            except Exception as e:
                self.lid_status.set_markup(
                    f"<span foreground='#FF4444'>❌ Fehler: {html.escape(str(e))}</span>"
                )
        except Exception as e:
            self.lid_status.set_markup(
                f"<span foreground='#FF4444'>❌ Fehler: {html.escape(str(e))}</span>"
            )

    def _read_lock_on_resume(self):
        """Prueft ob der Sleep-Hook aktiv ist."""
        return os.path.isfile(LOCK_HOOK_PATH) and os.access(LOCK_HOOK_PATH, os.X_OK)

    def on_lock_on_resume_toggled(self, widget):
        """Aktiviert oder deaktiviert den Sleep-Hook fuer Bildschirmsperre."""
        enable = widget.get_active()
        tmp_path = "/tmp/argon-lock-screen"
        try:
            if enable:
                with open(tmp_path, "w") as f:
                    f.write(LOCK_HOOK_CONTENT)
                bash_cmd = (
                    f"mv {tmp_path} {LOCK_HOOK_PATH} && "
                    f"chmod +x {LOCK_HOOK_PATH}"
                )
            else:
                bash_cmd = f"rm -f {LOCK_HOOK_PATH}"

            # Direkt versuchen (falls root)
            try:
                if enable:
                    os.makedirs(os.path.dirname(LOCK_HOOK_PATH), exist_ok=True)
                    shutil.move(tmp_path, LOCK_HOOK_PATH)
                    os.chmod(LOCK_HOOK_PATH, 0o755)
                else:
                    if os.path.exists(LOCK_HOOK_PATH):
                        os.remove(LOCK_HOOK_PATH)
                self.lock_status.set_markup(
                    "<span foreground='#44CC44'>✅ Gespeichert!</span>"
                )
                return
            except PermissionError:
                pass

            # Fallback: pkexec
            result = subprocess.run(
                ["pkexec", "bash", "-c", bash_cmd],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self.lock_status.set_markup(
                    "<span foreground='#44CC44'>✅ Gespeichert!</span>"
                )
            else:
                self.lock_status.set_markup(
                    "<span foreground='#FF4444'>❌ Fehler: Keine Root-Rechte erhalten.</span>"
                )
                widget.set_active(not enable)
        except subprocess.TimeoutExpired:
            self.lock_status.set_markup(
                "<span foreground='#FF4444'>❌ Zeitueberschreitung bei Authentifizierung.</span>"
            )
            widget.set_active(not enable)
        except Exception as e:
            self.lock_status.set_markup(
                f"<span foreground='#FF4444'>❌ Fehler: {html.escape(str(e))}</span>"
            )
            widget.set_active(not enable)

    def _write_control(self):
        """Schreibt Steuerbefehle nach /tmp/argon_dashboard_control."""
        data = {
            "fan_mode": self.fan_mode,
            "fan_speed": self.fan_speed,
            "kbd_backlight": self.kbd_backlight,
            "brightness": int(self.bright_adjustment.get_value())
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
                batt_str = f"{int(batt)}"
                if batt < 20:
                    batt_text = f"<span foreground='#FF4444'><b>{batt_str}%</b></span> {charge_icon}"
                elif batt < 50:
                    batt_text = f"<span foreground='#FF8800'><b>{batt_str}%</b></span> {charge_icon}"
                else:
                    batt_text = f"<span foreground='#44CC44'><b>{batt_str}%</b></span> {charge_icon}"
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

            # Ladestatus
            charging = data.get("is_charging")
            if charging is True:
                power_text = "<span foreground='#44CC44'><b>⚡ Laedt</b></span>"
            elif charging is False:
                power_text = "<span foreground='#FF8800'>🔋 Entlaedt</span>"
            else:
                power_text = "<span foreground='#888888'>–</span>"
            self.status_values[3].set_markup(power_text)

            # Restzeit
            time_remaining = data.get("time_remaining")
            if time_remaining is None:
                time_text = "<span foreground='#888888'>–</span>"
            else:
                h = int(time_remaining // 60)
                m = int(time_remaining % 60)
                if charging:
                    time_text = f"<span foreground='#44CC44'>Voll in <b>{h}:{m:02d} h</b></span>"
                else:
                    color = "#FF4444" if time_remaining < 30 else "#FF8800" if time_remaining < 60 else "#44CC44"
                    time_text = f"<span foreground='{color}'>Leer in <b>{h}:{m:02d} h</b></span>"
            self.status_values[4].set_markup(time_text)

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
            if hasattr(self, "kbd_switch") and kbd != self.kbd_switch.get_active():
                self.kbd_switch.set_active(kbd)
                self._update_kbd_label()

            # Helligkeit synchronisieren (nur wenn Nutzer nicht gerade geaendert hat)
            brightness = data.get("brightness")
            if brightness is not None:
                user_changed_recently = (time.time() - self._bright_changed_at) < 5.0
                if not user_changed_recently:
                    if int(self.bright_adjustment.get_value()) != int(brightness):
                        self.bright_adjustment.set_value(brightness)
                        self.bright_label.set_text(f"{int(brightness)}%")

            self._updating = False

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Status-Update Fehler: {e}", file=sys.stderr)
            self._updating = False

        return True  # Timer weiterlaufen lassen


LOCK_FILE = "/tmp/argon_control.lock"


def main():
    # Sicherstellen dass nur eine Instanz laeuft
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Bereits eine Instanz aktiv — Fenster in den Vordergrund holen nicht moeglich
        # ohne IPC, daher einfach beenden
        print("Argon Control Panel laeuft bereits.", file=sys.stderr)
        sys.exit(0)

    win = ArgonControlWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    lock_fd.close()


if __name__ == "__main__":
    main()
