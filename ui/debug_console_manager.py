"""
ui/debug_console_manager.py — Mengelola window-window DebugConsole.

Diambil dari main.py.App, yang tadinya menyimpan dict self._debug_consoles dan
menaruh semua logic buka/fokus/tutup/menu langsung sebagai method App (bagian
dari God Object). DebugConsoleManager berdiri sendiri: App hanya perlu compose
satu instance dan panggil method publiknya — App tidak perlu tahu detail
window-tracking atau layout grid-nya.
"""

import json
import os
import sys
import tkinter as tk

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
if _UI_DIR not in sys.path:
    sys.path.insert(0, _UI_DIR)

from debug_console import DebugConsole

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_CONFIG_JSON = os.path.join(_ROOT, "config", "config.json")

# Grid layout window: 2 kolom, 868x348 per window (termasuk gap).
_WIN_W, _WIN_H, _COLS = 868, 348, 2

_EXTRA_WINDOWS = {
    "all":          ("Debug — All Logs",    ""),
    "commands":     ("Debug — TM81 Cmd",    "commands"),
    "flash":        ("Debug — Flash",       "flash"),
    "test_loader":  ("Debug — Test Loader", "test_loader"),
}


class DebugConsoleManager:
    """Buka/fokus/tutup satu atau lebih window DebugConsole, identitas per key."""

    def __init__(self, root, on_change=None):
        self._root      = root                 # App (Tk root) — parent utk Toplevel
        self._consoles: dict = {}
        self._on_change = on_change            # dipanggil tiap window dibuka/ditutup

    # ------------------------------------------------------------------ query

    def has_any_open(self) -> bool:
        return any(w.winfo_exists() for w in self._consoles.values())

    @staticmethod
    def load_config() -> dict:
        try:
            with open(_APP_CONFIG_JSON, encoding="utf-8") as f:
                return json.load(f).get("debug", {})
        except Exception:
            return {}

    @staticmethod
    def _read_serial_connections() -> dict:
        try:
            with open(_APP_CONFIG_JSON, encoding="utf-8") as f:
                return json.load(f).get("serial", {}).get("connections", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------ actions

    def open_or_focus(self, key: str, title: str, name_filter: str = "",
                       level: str = "DEBUG", offset: tuple = None):
        existing = self._consoles.get(key)
        if existing and existing.winfo_exists():
            existing.lift()
            return existing

        win = DebugConsole(self._root, min_level=level, title=title, name_filter=name_filter)
        if offset:
            try:
                mx = self._root.winfo_rootx() + offset[0]
                my = self._root.winfo_rooty() + offset[1]
                win.geometry(f"+{mx}+{my}")
            except Exception:
                pass

        self._consoles[key] = win
        self._notify()

        orig_close = win._on_close

        def _on_close_hook(k=key, fn=orig_close):
            fn()
            self._consoles.pop(k, None)
            self._notify()

        win.protocol("WM_DELETE_WINDOW", _on_close_hook)
        return win

    def maybe_autostart(self):
        """Buka window debug otomatis saat startup jika config debug.enabled = 1.

        Semua window ditata grid _COLS-kolom, dan keseluruhan grid itu di-center
        ke layar (bukan cuma nempel di pojok window utama) — dihitung dari total
        window yang akan dibuka, supaya 1 window pun tetap center, dan banyak
        window tetap rapi tanpa saling menutupi.
        """
        cfg = self.load_config()
        if not cfg.get("enabled", 0):
            return
        level        = cfg.get("level", "DEBUG")
        serial_conns = self._read_serial_connections()

        # Kumpulkan dulu semua window yang akan dibuka, supaya ukuran grid
        # (dan karenanya titik center-nya) bisa dihitung sebelum ada yang dibuka.
        to_open = []
        for conn_name, conn_def in serial_conns.items():
            desc  = conn_def.get("description", conn_name)
            key   = f"serial.{conn_name}"
            title = f"Debug — {conn_name.upper()}  ({desc})"
            to_open.append((key, title, f"serial_comm.{conn_name}"))

        for wid in cfg.get("windows", []):
            if wid in _EXTRA_WINDOWS:
                title, nf = _EXTRA_WINDOWS[wid]
                to_open.append((wid, title, nf))

        if not to_open:
            return

        start_x, start_y = self._centered_grid_start(len(to_open))
        root_x, root_y   = self._root.winfo_rootx(), self._root.winfo_rooty()

        for i, (key, title, nf) in enumerate(to_open):
            col, row = i % _COLS, i // _COLS
            abs_x = start_x + col * _WIN_W
            abs_y = start_y + row * _WIN_H
            # open_or_focus menambahkan posisi root ke offset — konversi balik
            # supaya hasil akhirnya tetap koordinat layar absolut yang sudah di-center.
            offset = (abs_x - root_x, abs_y - root_y)
            self.open_or_focus(key, title, name_filter=nf, level=level, offset=offset)

        # Window debug baru dibuat di atas Test Point — angkat lagi window utama
        # ke depan supaya operator tidak perlu geser-geser window debug dulu
        # untuk mengakses Test Point. Ditunda sedikit (after) supaya dijalankan
        # SETELAH semua window debug selesai di-render oleh window manager —
        # kalau langsung, window debug yang belum sempat digambar bisa balik
        # menutupi lagi.
        self._root.after(150, self._refocus_root)

    def _refocus_root(self):
        """Angkat & fokuskan window utama (Test Point) ke depan.

        lift()/focus_force() saja kadang tidak cukup di Windows karena OS
        mencegah aplikasi background mencuri foreground focus — trik toggle
        'topmost' sebentar memaksa window manager benar-benar mengangkatnya.
        """
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.attributes("-topmost", True)
            self._root.after(50, lambda: self._root.attributes("-topmost", False))
            self._root.focus_force()
        except Exception:
            pass

    def _centered_grid_start(self, count: int) -> tuple:
        """Titik kiri-atas (screen-absolute) supaya grid berisi `count` window
        (_COLS kolom) ter-center di layar."""
        cols = min(_COLS, count)
        rows = -(-count // _COLS)  # ceil division
        grid_w = cols * _WIN_W
        grid_h = rows * _WIN_H
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = max(0, (sw - grid_w) // 2)
        y = max(0, (sh - grid_h) // 2)
        return x, y

    def build_menu(self, anchor_btn):
        """Bangun & tampilkan menu popup pilihan window debug, anchor ke tombol."""
        menu = tk.Menu(self._root, tearoff=0,
                       bg="#161b22", fg="#c9d1d9",
                       activebackground="#264f78", activeforeground="white",
                       font=("Consolas", 9))
        cfg          = self.load_config()
        level        = cfg.get("level", "DEBUG")
        serial_conns = self._read_serial_connections()

        if serial_conns:
            menu.add_command(label="── Serial ports ──", state="disabled")
        for conn_name, conn_def in serial_conns.items():
            desc   = conn_def.get("description", conn_name)
            key    = f"serial.{conn_name}"
            title  = f"Debug — {conn_name.upper()}  ({desc})"
            nf     = f"serial_comm.{conn_name}"
            active = key in self._consoles and self._consoles[key].winfo_exists()
            prefix = "✓ " if active else "  "
            menu.add_command(
                label=f"{prefix}{conn_name.upper()}  —  {desc}",
                command=lambda k=key, t=title, f=nf, lv=level:
                    self.open_or_focus(k, t, f, lv),
            )

        menu.add_separator()
        extras = [
            ("all",         "All logs",       ""),
            ("commands",    "TM81 commands",  "commands"),
            ("flash",       "Flash / STM32",  "flash"),
            ("test_loader", "Test loader",    "test_loader"),
        ]
        for key, label, nf in extras:
            active = key in self._consoles and self._consoles[key].winfo_exists()
            prefix = "✓ " if active else "  "
            menu.add_command(
                label=f"{prefix}{label}",
                command=lambda k=key, t=f"Debug — {label}", f=nf, lv=level:
                    self.open_or_focus(k, t, f, lv),
            )
        try:
            menu.tk_popup(anchor_btn.winfo_rootx(),
                          anchor_btn.winfo_rooty() + anchor_btn.winfo_height())
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------ internals

    def _notify(self):
        if self._on_change:
            self._on_change()
