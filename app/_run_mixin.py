"""RunMixin — sequential test run (Start/Stop/done callback)."""

import logging
from config import COLORS
from test_modules import TestResult

log = logging.getLogger("main")


class RunMixin:

    def _toggle_run(self):
        if not self._controller.is_seq_running():
            self._do_start()
        else:
            self._do_stop()

    def _do_start(self):
        self._save_tasks()
        rows = self._list_panel.get_rows()
        if not rows:
            return

        current_sn = self._device_var.get().strip()
        if current_sn and current_sn == self._resume_sn:
            for row in rows:
                if row.test_item.result != TestResult.OK:
                    row.reset()
            self._status_var.set("Melanjutkan dari step NG…")
        else:
            saved = self._load_resume_state()
            if current_sn and saved.get("sn") == current_sn:
                for row in rows:
                    row.reset()
                for idx in saved.get("ok_step_indices", []):
                    if 0 <= idx < len(rows):
                        rows[idx].set_result(TestResult.OK, ok_msg="(resumed)")
                self._resume_sn = current_sn
                self._status_var.set("Melanjutkan dari step NG (setelah restart)…")
            else:
                for row in rows:
                    row.reset()
                self._resume_sn = ""
                self._clear_resume_state()

        self._reset_db_session()
        self._toggle_btn.config(text="⏹  Stop", bg="#e67e22")
        self._controller.run_all(
            rows,
            done_callback=self._on_seq_done,
            scroll_fn=self._list_panel.scroll_to_row,
        )

    def _do_stop(self):
        rows = self._list_panel.get_rows()
        self._controller.stop_now(rows)
        self._toggle_btn.config(text="▶  Start", bg="#2980b9")
        self._status_var.set("Dihentikan")
        if hasattr(self, "_status_lbl"):
            self._status_lbl.config(fg=COLORS["warn"])
        self.after(3000, self._reset_status)

    def _reset_status(self):
        self._status_var.set("Ready")
        if hasattr(self, "_status_lbl"):
            self._status_lbl.config(fg=COLORS["sub"])

    def _on_seq_done(self, _):
        rows    = self._list_panel.get_rows()
        ng_rows = [r for r in rows if r.test_item.result == TestResult.NG]
        ok_rows = [r for r in rows if r.test_item.result == TestResult.OK]

        if ng_rows:
            self._resume_sn = self._device_var.get().strip()
            self._save_resume_state()
            ng_names = ", ".join(r.test_item.title for r in ng_rows)
            self._status_var.set(f"NG: {ng_names}")
            if hasattr(self, "_status_lbl"):
                self._status_lbl.config(fg=COLORS["ng"])
            self._finalize_db_session("NG")
        elif len(ok_rows) == len(rows):
            self._resume_sn = ""
            self._clear_resume_state()
            self._status_var.set("✔ Semua test PASS")
            if hasattr(self, "_status_lbl"):
                self._status_lbl.config(fg=COLORS["ok"])
            self._finalize_db_session("OK")
        else:
            self._resume_sn = ""
            self._status_var.set("Selesai")
            self._finalize_db_session(None)

        self._toggle_btn.config(text="▶  Start", bg="#2980b9")
        self.after(4000, self._reset_status)
