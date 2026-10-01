"""
ui/test_list_panel.py — Scrollable list of TestRowWidgets.
"""

import sys
import os

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import tkinter as tk
from tkinter import ttk

from config import COLORS
from ui.test_row_widget import TestRowWidget
from ui.scroll_util import bind_scroll, scroll_into_view


class TestListPanel(tk.Frame):
    """Scrollable list of TestRowWidgets."""

    def __init__(self, parent, scale: float, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.scale      = scale
        self.controller = controller
        self._rows: list[TestRowWidget] = []
        self._build()

    def _build(self):
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        self._canvas    = tk.Canvas(container, bg=COLORS["bg"], highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(container, orient="vertical",
                                        command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._auto_scrollbar)
        self._canvas.pack(fill="both", expand=True)

        self._inner  = tk.Frame(self._canvas, bg=COLORS["bg"])
        self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",  self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Scroll roda mouse: di-bind di level toplevel (lihat ui/scroll_util.py)
        # sehingga bekerja di posisi manapun dalam area list, lintas platform
        # (Windows <MouseWheel> maupun Linux/X11 <Button-4>/<Button-5>).
        bind_scroll(self._canvas, area=container)

    def _auto_scrollbar(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scrollbar.pack_forget()
        else:
            self._scrollbar.pack(side="right", fill="y")
            self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.set(first, last)

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._window, width=event.width)

    def load_tests(self, tests: list):
        """Rebuild seluruh list dari awal (restore / project switch / clear)."""
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows.clear()
        tk.Frame(self._inner, bg=COLORS["bg"], height=int(6 * self.scale)).pack()
        for i, item in enumerate(tests):
            row = TestRowWidget(
                self._inner, item, i,
                scale=self.scale,
                on_run_request=self._on_run_request,
                on_running=self.scroll_to_row,
            )
            self._rows.append(row)
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.yview_moveto(0)

    def append_row(self, item) -> None:
        """Tambah satu row tanpa rebuild seluruh list."""
        index = len(self._rows)
        row = TestRowWidget(
            self._inner, item, index,
            scale=self.scale,
            on_run_request=self._on_run_request,
            on_running=self.scroll_to_row,
        )
        self._rows.append(row)
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def get_rows(self) -> list:
        return self._rows

    def reset_all(self):
        for row in self._rows:
            row.reset()

    def refresh_validations(self):
        for row in self._rows:
            row.refresh_validation()

    def scroll_to_row(self, row) -> None:
        """Bawa `row` ke dalam viewport kalau sedang kepotong.

        Dipasang sebagai `on_running` tiap TestRowWidget, jadi saat sequence
        Start jalan, list otomatis mengikuti test yang sedang berjalan.
        Dijadwalkan lewat after(0) supaya geometry row (progress bar dll yang
        baru muncul saat Running) sudah final waktu posisinya dihitung.
        """
        frame = getattr(row, "frame", None)
        if frame is None:
            return
        self.after(0, lambda: scroll_into_view(
            self._canvas, frame, margin=int(10 * self.scale)))

    def _on_run_request(self, row: TestRowWidget):
        self.controller.run_test(row)
