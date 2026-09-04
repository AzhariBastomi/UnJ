"""
ui/dialogs/add_test.py — AddTestDialog
"""

import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import tkinter as tk
from tkinter import ttk
from config import COLORS
from ui.scroll_util import bind_scroll
from ui.popup_util import TouchPopupMixin
from project import module_project, detect_project
from test_loader import (
    discover_tests, load_test,
    get_flash_sources,
    get_voltage_sources,
    load_tm81_tests,      tm81_module_names,      tm81_label,
    get_tm81_extra_sources,
    load_bexa_tests,      bexa_module_names,      bexa_label,
)

# Type badge colors — tetap hardcode karena ini warna semantik bukan tema
_TYPE_BG = {
    "progress": "#3498db",
    "manual":   "#8e44ad",
    "auto":     "#27ae60",
}


class AddTestDialog(TouchPopupMixin, tk.Toplevel):
    """
    Picker dialog — tiap modul punya tombol Add sendiri.
    Project logic: hanya satu project (tm81/flash) aktif sekaligus.
    Universal tasks (voltage, dll.) selalu bisa ditambahkan.
    """

    def __init__(self, parent, on_add, on_add_batch=None, current_project: "str | None" = None):
        super().__init__(parent)
        self.title("Add Test")
        self.resizable(False, True)
        self.transient(parent)   # tetap di atas parent, tapi klik luar tidak diblokir
        self.configure(bg=COLORS["surface"])

        self._on_add          = on_add
        self._on_add_batch    = on_add_batch   # callback batch: list[(item, name)] → None
        self._current_project = current_project
        self._modules         = discover_tests()
        self._build()
        self.update_idletasks()

        # Batasi tinggi terhadap parent DAN layar — pada preset 7 inch window
        # utama bisa lebih besar dari panel fisiknya (content bisa di-scroll).
        _max_h = max(240, min(parent.winfo_height() - 80,
                              self.winfo_screenheight() - 40))
        if self.winfo_height() > _max_h:
            self.geometry(f"{self.winfo_width()}x{_max_h}")

        self.place_over_parent(parent)
        # Aktivasi window + close-on-outside-click ramah sentuh
        # (lihat ui/popup_util.py)
        self.init_popup_behavior()
        self.bind("<Escape>", lambda e: self.destroy())

    def _btn_state(self, proj: "str | None") -> str:
        if proj is None:
            return "normal"
        if self._current_project is None or self._current_project == proj:
            return "normal"
        return "disabled"

    def _build(self):
        self.minsize(560, 0)  # pastikan kolom tombol + Add tidak terpotong
        C = COLORS

        # ── Header (di luar area scroll) ───────────────────────────────────
        if self._current_project:
            msg = {
                "tm81":        "Project aktif: TM81  (flash / OTA / BEXA tidak bisa ditambahkan)",
                "flash":       "Project aktif: Flash  (tm81 / OTA / BEXA tidak bisa ditambahkan)",
                "tm81_ota":    "Project aktif: TM81 OTA  (tm81 / flash / BEXA tidak bisa ditambahkan)",
                "tm81_ota2":   "Project aktif: TM81 OTA2  (tm81 / flash / BEXA tidak bisa ditambahkan)",
                "tm81_ota_bl": "Project aktif: TM81 OTA BL  (tm81 / flash / BEXA tidak bisa ditambahkan)",
                "bexa":        "Project aktif: BEXA  (tm81 / flash / OTA tidak bisa ditambahkan)",
                "tm81_join":   "Project aktif: TM81 Join  (flash / OTA / BEXA tidak bisa ditambahkan)",
            }.get(self._current_project, f"Project aktif: {self._current_project}")
            tk.Label(self, text=msg, font=("TkDefaultFont", 9), fg=C["sub"],
                     bg=C["surface"], pady=4, anchor="w").pack(fill="x", padx=12)
            tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=0)

        tk.Label(self, text="Pilih test module:",
                 font=("TkDefaultFont", 12, "bold"), pady=10,
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=14)

        # ── Scrollable content area ─────────────────────────────────────────
        _container = tk.Frame(self, bg=C["surface"])
        _container.pack(fill="both", expand=True)

        _canvas = tk.Canvas(_container, highlightthickness=0, bg=C["surface"])
        _vsb    = ttk.Scrollbar(_container, orient="vertical", command=_canvas.yview)
        _inner  = tk.Frame(_canvas, bg=C["surface"])

        _inner_id = _canvas.create_window((0, 0), window=_inner, anchor="nw")

        _inner.bind("<Configure>",
                    lambda e: _canvas.configure(scrollregion=_canvas.bbox("all")))
        _canvas.bind("<Configure>",
                     lambda e: _canvas.itemconfig(_inner_id, width=e.width))

        _canvas.configure(yscrollcommand=_vsb.set)
        _canvas.pack(side="left", fill="both", expand=True)
        _vsb.pack(side="right", fill="y")

        # Mousewheel scroll — di-bind di toplevel dialog ini (ui/scroll_util.py),
        # jadi bekerja di posisi manapun dalam popup dan mendukung Linux/X11
        # (<Button-4>/<Button-5>) selain <MouseWheel> Windows/macOS.
        bind_scroll(_canvas, area=_container)

        # ── Row builder ──────────────────────────────────────────────────────
        _ri = [0]

        def _row(label_text, type_tag, detail, state, cmd):
            ri    = _ri[0]
            is_ok = state == "normal"
            fg    = C["text"] if is_ok else C["sub"]
            badge_bg = _TYPE_BG.get(type_tag, C["pending"]) if is_ok else C["pending"]
            row_bg   = C["surface"]

            # Ukuran baris dan tombol dibuat lega agar nyaman ditekan dengan jari
            tk.Label(_inner, text=label_text, font=("TkDefaultFont", 12, "bold"),
                     anchor="w", width=22, fg=fg, bg=row_bg).grid(
                row=ri, column=0, sticky="w", padx=(14, 4), pady=9)
            tk.Label(_inner, text=type_tag,
                     bg=badge_bg, fg="white",
                     font=("TkDefaultFont", 9), padx=8, pady=4).grid(
                row=ri, column=1, padx=4, sticky="w")
            tk.Label(_inner, text=detail, font=("TkFixedFont", 10), fg=C["sub"],
                     bg=row_bg, anchor="w", width=13).grid(
                row=ri, column=2, sticky="w", padx=4)
            tk.Button(_inner, text="+ Add", width=7,
                      font=("TkDefaultFont", 12, "bold"),
                      bg=C["ok"] if is_ok else C["pending"],
                      fg="white", relief="flat", bd=0,
                      activebackground=C["ok"] if is_ok else C["pending"],
                      activeforeground="white",
                      cursor="hand2" if is_ok else "",
                      padx=6, pady=10,
                      state=state, command=cmd).grid(
                row=ri, column=3, padx=(8, 14), pady=6, sticky="e")

            # Garis pemisah antar baris agar tetap terbaca saat baris melebar
            tk.Frame(_inner, height=1, bg=C["border"]).grid(
                row=ri + 1, column=0, columnspan=4, sticky="ew", padx=10)
            _ri[0] += 2

        # ── Grid column config ───────────────────────────────────────────────
        _inner.columnconfigure(0, weight=1)

        # Flash — satu baris per source (per JSON file)
        for _fsrc in get_flash_sources():
            _fnames = _fsrc.module_names()
            if not _fnames:
                continue
            st = self._btn_state("flash")
            _row(f"Flash {_fsrc.label()} ({len(_fnames)} region)", "progress",
                 f"{len(_fnames)} region", st,
                 lambda s=_fsrc: self._add_all_from_source(s))

        # Voltage — satu baris per source (per JSON file)
        for _vsrc in get_voltage_sources():
            _vnames = _vsrc.module_names()
            if not _vnames:
                continue
            _row(f"Voltage {_vsrc.label()}", "auto",
                 _vnames[0], "normal",
                 lambda s=_vsrc: self._add_all_from_source(s))

        # TM81 core
        tm81_names = tm81_module_names()
        if tm81_names:
            st  = self._btn_state("tm81")
            lbl = tm81_label()
            _row(f"{lbl} ({len(tm81_names)} test)", "auto",
                 f"{len(tm81_names)} entry", st, self._add_all_tm81)

        # Auto-discovered TM81 extra sources (OTA, Join, dll.)
        for _src in get_tm81_extra_sources():
            _names = _src.module_names()
            if not _names:
                continue
            _lbl  = _src.label()
            _proj = module_project(f"{_src.prefix}:_") or _src.prefix
            _st   = self._btn_state(_proj)
            _has_progress = any(
                e.get("type", "auto") == "progress"
                for e in _src.read_json().get("tests", [])
            )
            _badge = "progress" if _has_progress else "auto"
            _row(f"{_lbl} ({len(_names)} test)", _badge,
                 f"{len(_names)} entry", _st,
                 lambda s=_src: self._add_all_from_source(s))

        # BEXA — via Bluetooth SPP
        bexa_names = bexa_module_names()
        if bexa_names:
            st  = self._btn_state("bexa")
            lbl = bexa_label()
            _row(f"{lbl} ({len(bexa_names)} test)", "auto",
                 f"{len(bexa_names)} entry", st, self._add_all_bexa)

        # Universal discovered tests
        for name, label, mod in self._modules:
            mod_proj = module_project(name)
            st       = self._btn_state(mod_proj)
            ttype    = getattr(mod, "TYPE", "auto")
            cmd      = getattr(mod, "COMMAND", "?")
            _row(label, ttype, cmd, st, lambda n=name: self._add(n))

        # ── Footer (di luar area scroll) ────────────────────────────────────
        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x")
        tk.Button(self, text="Tutup", width=10, command=self.destroy,
                  bg=C["header_bg"], fg=C["header_fg"], relief="flat", bd=0,
                  font=("TkDefaultFont", 12), pady=12,
                  cursor="hand2").pack(pady=(8, 12))

    def _add(self, module_name: str):
        self._on_add(load_test(module_name), module_name)
        self.destroy()

    def _add_all_tm81(self):
        items_and_names = list(zip(load_tm81_tests(), tm81_module_names()))
        if self._on_add_batch:
            self._on_add_batch(items_and_names)
        else:
            for item, name in items_and_names:
                self._on_add(item, name)
        self.destroy()

    def _add_all_from_source(self, src):
        """Generic handler untuk semua auto-discovered TM81 sources."""
        items_and_names = list(zip(src.load_all(), src.module_names()))
        if self._on_add_batch:
            self._on_add_batch(items_and_names)
        else:
            for item, name in items_and_names:
                self._on_add(item, name)
        self.destroy()

    def _add_all_bexa(self):
        items_and_names = list(zip(load_bexa_tests(), bexa_module_names()))
        if self._on_add_batch:
            self._on_add_batch(items_and_names)
        else:
            for item, name in items_and_names:
                self._on_add(item, name)
        self.destroy()
