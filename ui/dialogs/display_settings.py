"""
ui/dialogs/display_settings.py — DisplaySettingsDialog
"""

import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ))
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import tkinter as tk
from tkinter import ttk
from config import DISPLAY_PRESETS, COLORS
from ui.popup_util import TouchPopupMixin


class DisplaySettingsDialog(TouchPopupMixin, tk.Toplevel):
    """Popup to change display preset or enter a custom resolution."""

    _MIN_W, _MIN_H = 320, 240

    def __init__(self, parent, current_preset: str, on_apply):
        super().__init__(parent)
        self.title("Display Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(bg=COLORS["surface"])

        self._on_apply   = on_apply
        self._preset_var = tk.StringVar(value=current_preset)
        # StringVar, bukan IntVar: IntVar.get() melempar TclError bila entry
        # dikosongkan, dan Apply jadi gagal diam-diam.
        _cur_w, _cur_h = DISPLAY_PRESETS.get(current_preset, (800, 480))
        self._w_var = tk.StringVar(value=str(_cur_w))
        self._h_var = tk.StringVar(value=str(_cur_h))

        # Ukuran kontrol menyesuaikan tinggi layar: pada panel 3 inch (320 px)
        # tombol setinggi panel 5/7 inch akan mendorong Apply keluar layar.
        _sh = self.winfo_screenheight()
        if _sh < 400:
            self._fs, self._pad_y, self._gap = 10, 6, 1
        elif _sh < 560:
            self._fs, self._pad_y, self._gap = 11, 10, 2
        else:
            self._fs, self._pad_y, self._gap = 12, 14, 3

        self._build()
        self._update_custom_state()
        self.place_over_parent(parent)

        # Close-on-outside-click aktif, sama seperti popup lain. Dulu ini
        # dimatikan karena pada preset 7 inch popup bisa terlempar ke luar layar
        # sehingga tap yang sah dinilai "di luar"; akar masalahnya sudah
        # ditangani place_over_parent() yang menjaga popup tetap utuh di layar.
        self.init_popup_behavior()
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self):
        C = COLORS

        tk.Label(self, text="Display Preset",
                 font=("TkDefaultFont", self._fs, "bold"),
                 bg=C["surface"], fg=C["text"]).grid(
            row=0, column=0, columnspan=2, pady=(14, 8), padx=16, sticky="w"
        )

        # Tombol besar, bukan radiobutton: indikator radio terlalu kecil untuk
        # ditekan dengan jari. Preset terpilih ditandai lewat warna tombol.
        self._preset_btns = {}
        row = 1
        for name in DISPLAY_PRESETS:
            btn = tk.Button(
                self, text=name, font=("TkDefaultFont", self._fs),
                relief="flat", bd=0, anchor="w", justify="left",
                padx=16, pady=self._pad_y, cursor="hand2",
                command=lambda n=name: self._select(n),
            )
            btn.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=self._gap)
            self._preset_btns[name] = btn
            row += 1

        tk.Frame(self, height=1, bg=C["border"]).grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=10)
        row += 1

        tk.Label(self, text="Custom Width:", font=("TkDefaultFont", 11),
                 bg=C["surface"], fg=C["sub"]).grid(
            row=row, column=0, padx=(16, 6), sticky="e", pady=4)
        self._w_entry = self._make_entry(self._w_var)
        self._w_entry.grid(row=row, column=1, padx=(0, 16), sticky="w", ipady=6)
        row += 1

        tk.Label(self, text="Custom Height:", font=("TkDefaultFont", 11),
                 bg=C["surface"], fg=C["sub"]).grid(
            row=row, column=0, padx=(16, 6), sticky="e", pady=4)
        self._h_entry = self._make_entry(self._h_var)
        self._h_entry.grid(row=row, column=1, padx=(0, 16), sticky="w", ipady=6)
        row += 1

        self._err_lbl = tk.Label(self, text="", bg=C["surface"], fg=C["ng"],
                                 font=("TkDefaultFont", 10))
        self._err_lbl.grid(row=row, column=0, columnspan=2, padx=16, sticky="w")
        row += 1

        btn_frame = tk.Frame(self, bg=C["surface"])
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(8, 14))
        tk.Button(btn_frame, text="Apply", width=9, command=self._apply,
                  bg=C["ok"], fg="white", relief="flat", bd=0,
                  font=("TkDefaultFont", self._fs, "bold"),
                  padx=10, pady=max(6, self._pad_y - 2),
                  cursor="hand2").pack(side="left", padx=8)
        tk.Button(btn_frame, text="Cancel", width=9, command=self.destroy,
                  bg=C["card"], fg=C["sub"], relief="flat", bd=0,
                  font=("TkDefaultFont", self._fs),
                  padx=10, pady=max(6, self._pad_y - 2),
                  cursor="hand2").pack(side="left", padx=8)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

    def _make_entry(self, var) -> tk.Entry:
        C = COLORS
        return tk.Entry(
            self, textvariable=var, width=6,
            font=("TkDefaultFont", self._fs + 1),
            bg=C["card"], fg=C["text"], insertbackground=C["text"],
            relief="flat", highlightthickness=1,
            highlightbackground=C["border"], highlightcolor=C["running"],
        )

    def _select(self, name: str):
        """Pilih preset lewat tap di baris manapun (bukan hanya indikator)."""
        self._preset_var.set(name)
        self._update_custom_state()

    def _update_custom_state(self):
        C       = COLORS
        current = self._preset_var.get()
        for name, btn in self._preset_btns.items():
            picked = (name == current)
            btn.config(
                bg=C["running"] if picked else C["card"],
                fg="white"      if picked else C["text"],
                activebackground=C["running"] if picked else C["card_hov"],
                activeforeground="white" if picked else C["text"],
                font=("TkDefaultFont", self._fs,
                      "bold" if picked else "normal"),
            )
        state = "normal" if current == "Custom" else "disabled"
        self._w_entry.config(state=state)
        self._h_entry.config(state=state)
        self._err_lbl.config(text="")

    @staticmethod
    def _as_int(value: str, fallback: int) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return fallback

    def _apply(self):
        preset = self._preset_var.get()
        if preset not in DISPLAY_PRESETS:
            self._err_lbl.config(text="Preset belum dipilih.")
            return

        if preset == "Custom":
            w = self._as_int(self._w_var.get(), 0)
            h = self._as_int(self._h_var.get(), 0)
            if w < self._MIN_W or h < self._MIN_H:
                self._err_lbl.config(
                    text=f"Ukuran minimal {self._MIN_W}x{self._MIN_H}.")
                return
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h   = min(w, sw), min(h, sh)
        else:
            w, h = DISPLAY_PRESETS[preset]

        self.destroy()          # lepas grab dulu agar window utama bisa di-resize
        self._on_apply(preset, w, h)
