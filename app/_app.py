"""App — root window, __init__, dan helpers kecil.

Semua method besar di-delegate ke mixin:
  BuildMixin     — _build_*, input callbacks, _update_start_btn
  RunMixin       — _toggle_run, _do_start, _do_stop, _on_seq_done
  DbMixin        — _new_db_session, _finalize_db_session, _reset_db_session
  StateMixin     — resume state, _save_tasks, _load_tasks
  SettingsMixin  — dialog settings, _refresh_dynamic_buttons
  TestMgmtMixin  — _add_test, _clear_all, _reset_project_config
"""

import os, threading, logging
import tkinter as tk

from config import DISPLAY_PRESETS, DEFAULT_PRESET, FONT_SCALE, COLORS
import test_loader

from controllers.keepalive       import KeepaliveManager
from controllers.test_controller import TestController
from ui.debug_console_manager    import DebugConsoleManager
from ui.touch_click              import enable_touch_click
from ui.pointer_util             import install_pointer_probe, install_event_trace
from task_store                  import TaskStore

from app._constants      import APP_VERSION
import app._registrations  # noqa: F401 — isi btn_registry saat startup
from app._build_mixin    import BuildMixin
from app._run_mixin      import RunMixin
from app._db_mixin       import DbMixin
from app._state_mixin    import StateMixin
from app._settings_mixin import SettingsMixin
from app._test_mgmt_mixin import TestMgmtMixin

log = logging.getLogger("main")


class App(BuildMixin, RunMixin, DbMixin, StateMixin, SettingsMixin, TestMgmtMixin, tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"Test Point  v{APP_VERSION}")
        self.configure(bg=COLORS["bg"])
        # Layar sentuh: tombol Tk baru jalan kalau Tk yakin pointer ada di
        # atasnya (event <Enter>), padahal tap jari sering tidak menghasilkan
        # crossing event. Tanpa ini, tap pertama pada popup/messagebox tidak
        # melakukan apa-apa sampai layar digeser sekali. Lihat ui/touch_click.py.
        enable_touch_click(self)
        # Merekam gerakan pointer tanpa tombol (hover). Dipakai popup
        # untuk membedakan mouse dari layar sentuh: hanya di layar
        # sentuh pointer perlu dipindahkan ke dalam popup saat muncul.
        install_pointer_probe(self)
        install_event_trace(self, "main")
        self.report_callback_exception = self._on_tk_error

        self._preset       = DEFAULT_PRESET
        self._scale        = FONT_SCALE[DEFAULT_PRESET]
        self._display_w, self._display_h = DISPLAY_PRESETS[DEFAULT_PRESET]
        self._test_names   : list[str]      = []
        self._tests        : list           = []
        self._station      : str            = ""
        self._project      : "str | None"   = None

        self._controller     = TestController()
        self._keepalive      = KeepaliveManager()
        self._debug_consoles = DebugConsoleManager(self, on_change=self._update_debug_btn)
        self._task_store     = TaskStore()
        self._resume_sn      = ""
        self._RESUME_FILE    = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config", "resume_state.json"
        )
        self._station_save_id = None
        self._station_ctx_id  = None

        self._load_tasks()

        self._center_on_screen(self._display_w, self._display_h)
        self.minsize(320, 240)
        self.resizable(self._preset == "Custom", self._preset == "Custom")

        self._build()
        test_loader.set_tk_root(self)
        test_loader.watch_context(
            "device_id",
            lambda v: self._device_var.set(v),
        )
        self._refresh_dynamic_buttons()
        self.after(500, self._auto_connect)
        self.after(200, self._maybe_open_debug_console)
        # Operator langsung bisa scan tanpa klik field dulu.
        self.after(300, self._focus_sn)

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _center_on_screen(self, w: int, h: int):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(0, (sw - w) // 2)
        y  = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_tk_error(self, exc_type, exc_val, exc_tb):
        import traceback
        log.error("Exception dalam Tkinter callback:")
        log.error("".join(traceback.format_exception(exc_type, exc_val, exc_tb)))

    # ------------------------------------------------------------------
    # Auto-connect serial
    # ------------------------------------------------------------------

    def _auto_connect(self):
        """Scan semua koneksi dari config.json, retry tiap 5 detik."""
        _RETRY_MS = 5_000

        def _do():
            import serial_manager as sm
            import serial.tools.list_ports as lp

            try:
                all_ports = list(lp.comports())
            except Exception:
                all_ports = []

            def find_port(device_name: str) -> str:
                kw = device_name.lower()
                for p in all_ports:
                    if (kw in (p.description or "").lower() or
                            kw in (p.manufacturer or "").lower() or
                            kw in (p.product or "").lower()):
                        return p.device
                return ""

            any_failed = False
            for name, cfg in sm._CONN_DEFS.items():
                if sm.is_connected(name):
                    continue
                dev_name = cfg.get("device_name", "")
                found    = find_port(dev_name)
                ok = False
                try:
                    ok = sm.connect(name)
                except Exception as e:
                    self.after(0, lambda n=name, e=e:
                        log.warning("[serial] connect(%r) error: %s", n, e))
                status = f"OK [{found}]" if ok else f"NG (cari: {dev_name!r})"
                self.after(0, lambda n=name, s=status:
                    log.info("[serial] %s: %s", n, s))
                if not ok:
                    any_failed = True

            if any_failed:
                self.after(_RETRY_MS, self._auto_connect)

        threading.Thread(target=_do, daemon=True).start()
