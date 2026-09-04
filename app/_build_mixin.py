"""BuildMixin — semua method _build_* dan update UI input area."""

import logging
import tkinter as tk

from config import BASE_FONTS, COLORS
import test_loader

log = logging.getLogger("main")


class BuildMixin:
    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        self._build_header()
        self._build_input_area()
        self._build_action_bar()
        self._build_test_list()

    # -- Layout sub-builders -------------------------------------------

    def _build_header(self):
        """Top bar: title, project label, dynamic buttons, debug/display/add."""
        fs = lambda k: max(7, int(BASE_FONTS[k] * self._scale))

        top = tk.Frame(self, bg=COLORS["header_bg"], pady=4)
        top.pack(fill="x")

        tk.Label(
            top, text="Test Point", bg=COLORS["header_bg"], fg="white",
            font=("TkDefaultFont", fs("title"), "bold"),
        ).pack(side="left", padx=10)

        proj_text = f"  [{self._project.upper()}]" if self._project else ""
        self._proj_lbl = tk.Label(
            top, text=proj_text,
            bg=COLORS["header_bg"], fg="#f39c12",
            font=("TkDefaultFont", fs("small"), "bold"),
        )
        self._proj_lbl.pack(side="left")

        self._dyn_btns = tk.Frame(top, bg=COLORS["header_bg"])

        self._display_btn = tk.Button(
            top, text="⚙ Display", command=self._open_display_settings,
            bg=COLORS["header_bg"], fg="white", relief="flat",
            font=("TkDefaultFont", fs("button")), cursor="hand2",
        )
        self._display_btn.pack(side="right", padx=6)

        self._debug_btn = tk.Button(
            top, text="🐛 Debug", command=self._toggle_debug_console,
            bg=COLORS["header_bg"], fg="#6e7681", relief="flat",
            font=("TkDefaultFont", fs("button")), cursor="hand2",
        )
        self._debug_btn.pack(side="right", padx=6)

        tk.Button(
            top, text="+ Add Test", command=self._open_add_test,
            bg="#27ae60", fg="white", relief="flat",
            font=("TkDefaultFont", fs("button")), cursor="hand2",
            padx=10, pady=3,
        ).pack(side="right", padx=6)

    def _build_input_area(self):
        """Device ID dan Station entry fields."""
        fs = lambda k: max(7, int(BASE_FONTS[k] * self._scale))

        _inp_wrap = tk.Frame(self, bg=COLORS["surface"])
        _inp_wrap.pack(fill="x")
        inp_frame = tk.Frame(_inp_wrap, bg=COLORS["surface"], pady=6)
        inp_frame.pack(fill="x", padx=10)
        tk.Frame(_inp_wrap, height=1, bg=COLORS["border"]).pack(fill="x")

        tk.Label(
            inp_frame, text="Device ID / Serial No.:",
            bg=COLORS["surface"], fg=COLORS["text"],
            font=("TkDefaultFont", fs("label")),
        ).pack(side="left")

        self._device_var = tk.StringVar()
        self._validation_after_id = None  # debounce handle

        def _on_device_change(*_):
            new_val = self._device_var.get()
            if test_loader.get_context("device_id") == new_val:
                return
            if self._validation_after_id:
                self.after_cancel(self._validation_after_id)
            self._validation_after_id = self.after(150, self._deferred_sn_update)

        self._device_var.trace_add("write", _on_device_change)
        _dev_entry = tk.Entry(
            inp_frame, textvariable=self._device_var,
            font=("TkDefaultFont", fs("label")), width=20,
            bg=COLORS["card"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat",
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["running"],
        )
        _dev_entry.pack(side="left", padx=6, ipady=3)
        _dev_entry.bind("<FocusOut>", lambda _: self._on_device_change())
        _dev_entry.bind("<Return>",   lambda _: self._on_device_change())
        _dev_entry.bind("<Control-a>", lambda e: (
            e.widget.select_range(0, "end"), e.widget.icursor("end"), "break"
        ))

        tk.Label(
            inp_frame, text="Station:",
            bg=COLORS["surface"], fg=COLORS["text"],
            font=("TkDefaultFont", fs("label")),
        ).pack(side="left", padx=(12, 0))

        self._station_var = tk.StringVar(value=self._station)
        self._station_var.trace_add("write", self._on_station_change)
        _sta_entry = tk.Entry(
            inp_frame, textvariable=self._station_var,
            font=("TkDefaultFont", fs("label")), width=28,
            bg=COLORS["card"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat",
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["running"],
        )
        _sta_entry.pack(side="left", padx=6, ipady=3)
        _sta_entry.bind("<Return>", lambda _: self._save_tasks())
        _sta_entry.bind("<Control-a>", lambda e: (
            e.widget.select_range(0, "end"), e.widget.icursor("end"), "break"
        ))

    def _build_action_bar(self):
        """Start/Stop button, Clear, status label, keepalive LED."""
        fs = lambda k: max(7, int(BASE_FONTS[k] * self._scale))

        _act_wrap = tk.Frame(self, bg=COLORS["surface"])
        _act_wrap.pack(fill="x")
        act_frame = tk.Frame(_act_wrap, bg=COLORS["surface"], pady=4)
        act_frame.pack(fill="x", padx=10)
        tk.Frame(_act_wrap, height=1, bg=COLORS["border"]).pack(fill="x")

        self._toggle_btn = tk.Button(
            act_frame, text="▶  Start",
            command=self._toggle_run,
            bg="#2980b9", fg="white", relief="flat",
            font=("TkDefaultFont", fs("button")),
            padx=12, pady=6, cursor="hand2",
            state="disabled",
        )
        self._toggle_btn.pack(side="left")

        _sep = tk.Frame(act_frame, width=1, bg=COLORS["border"])
        _sep.pack(side="left", fill="y", padx=8, pady=4)

        tk.Button(
            act_frame, text="🗑  Clear",
            command=self._clear_all,
            bg="#c0392b", fg="white", relief="flat",
            font=("TkDefaultFont", fs("button")),
            padx=10, pady=6, cursor="hand2",
        ).pack(side="left")

        self._status_var = tk.StringVar(value="Ready")
        self._status_lbl = tk.Label(
            act_frame, textvariable=self._status_var,
            bg=COLORS["surface"], fg=COLORS["sub"],
            font=("TkDefaultFont", fs("small")),
        )
        self._status_lbl.pack(side="right", padx=(0, 4))

        self._ka_led = tk.Label(
            act_frame, text="●",
            bg=COLORS["surface"], fg=COLORS.get("border", "#444"),
            font=("TkDefaultFont", fs("small")),
        )
        self._ka_led.pack(side="right", padx=(0, 2))

        def _on_ka_status(ok: bool):
            color = "#2ecc71" if ok else "#e74c3c"
            self.after(0, lambda: self._ka_led.config(fg=color))

        self._keepalive.set_status_callback(_on_ka_status)

    def _build_test_list(self):
        """Scrollable test list panel + initial data load."""
        from ui.test_list_panel import TestListPanel
        self._list_panel = TestListPanel(
            self, scale=self._scale, controller=self._controller,
            bg=COLORS["bg"],
        )
        self._list_panel.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._list_panel.load_tests(self._tests)
        self._list_panel.refresh_validations()
        self._refresh_dynamic_buttons()
        self._update_start_btn()

    def _refresh_project_label(self):
        if hasattr(self, "_proj_lbl"):
            self._proj_lbl.config(
                text=f"  [{self._project.upper()}]" if self._project else ""
            )

    # ------------------------------------------------------------------
    # Input callbacks
    # ------------------------------------------------------------------

    def _deferred_sn_update(self):
        """Dipanggil 150ms setelah user berhenti mengetik SN."""
        test_loader.update_context({"device_id": self._device_var.get()})
        self._update_start_btn()
        if hasattr(self, "_list_panel"):
            self._list_panel.refresh_validations()

    def _on_device_change(self, *_):
        """FocusOut / Return — siapkan DB session baru (background thread)."""
        import threading
        test_loader.update_context({"device_id": self._device_var.get()})
        threading.Thread(
            target=self._new_db_session, kwargs={"force_new": False}, daemon=True
        ).start()

    def _on_station_change(self, *_):
        self._station = self._station_var.get()
        if self._station_ctx_id:
            self.after_cancel(self._station_ctx_id)
        _val = self._station
        self._station_ctx_id = self.after(
            150, lambda: test_loader.update_context({"station": _val})
        )
        if self._station_save_id:
            self.after_cancel(self._station_save_id)
            self._station_save_id = None

    # ------------------------------------------------------------------
    # Start button enable/disable
    # ------------------------------------------------------------------

    def invalidate_fw_cache(self):
        self._fw_ok_cache = None

    def _update_start_btn(self):
        """Enable/disable tombol Start berdasarkan SN, fw_version, dan test list."""
        import os, json as _json
        if not hasattr(self, "_toggle_btn") or not hasattr(self, "_device_var"):
            return
        sn        = self._device_var.get().strip()
        has_tests = bool(self._test_names)
        has_tm81  = any(
            n.startswith("tm81:") or n.startswith("tm81_")
            for n in self._test_names
        )
        sn_ok = sn or not has_tm81

        fw_ok = getattr(self, "_fw_ok_cache", None)
        if fw_ok is None:
            fw_ok = True
            _ota_proj = next(
                (p.rstrip(":") for p in ("tm81_ota:", "tm81_ota2:", "tm81_ota_bl:") if self._project == p.rstrip(":")),
                None
            )
            if _ota_proj:
                try:
                    _ota_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "..", "commands", "tm81", "config", f"{_ota_proj}.json"
                    )
                    with open(_ota_path, encoding="utf-8") as _f:
                        fw_ok = bool(_json.load(_f).get("fw_version", "").strip())
                except Exception:
                    fw_ok = False
            self._fw_ok_cache = fw_ok

        if has_tests and sn_ok and fw_ok:
            self._toggle_btn.config(state="normal", bg="#2980b9")
        else:
            if not self._controller.is_seq_running():
                self._toggle_btn.config(state="disabled", text="▶  Start", bg="#7f8c8d")

    # ------------------------------------------------------------------
    # Debug console passthrough
    # ------------------------------------------------------------------

    def _maybe_open_debug_console(self):
        self._debug_consoles.maybe_autostart()

    def _toggle_debug_console(self):
        self._debug_consoles.build_menu(self._debug_btn)

    def _update_debug_btn(self):
        if not hasattr(self, "_debug_btn"):
            return
        any_open = self._debug_consoles.has_any_open()
        self._debug_btn.config(fg="#58a6ff" if any_open else "#6e7681")
