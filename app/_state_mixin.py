"""StateMixin — resume state (file) dan persist tasks."""

import os, json, logging
from test_modules import TestResult

log = logging.getLogger("main")


class StateMixin:

    # ------------------------------------------------------------------
    # Resume state — persisten ke file
    # ------------------------------------------------------------------

    def _save_resume_state(self):
        rows = self._list_panel.get_rows()
        ok_indices = [i for i, r in enumerate(rows)
                      if r.test_item.result == TestResult.OK]
        state = {
            "sn":              self._device_var.get().strip(),
            "ok_step_indices": ok_indices,
        }
        try:
            os.makedirs(os.path.dirname(self._RESUME_FILE), exist_ok=True)
            with open(self._RESUME_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.warning("Gagal simpan resume state: %s", e)

    def _load_resume_state(self) -> dict:
        try:
            with open(self._RESUME_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _clear_resume_state(self):
        try:
            if os.path.isfile(self._RESUME_FILE):
                os.remove(self._RESUME_FILE)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Persist tasks (station, project, test list, display preset)
    # ------------------------------------------------------------------

    def _save_tasks(self):
        self._task_store.save({
            "station":   getattr(self, "_station", ""),
            "project":   getattr(self, "_project", None),
            "tests":     self._test_names,
            "preset":    getattr(self, "_preset", ""),
            "display_w": getattr(self, "_display_w", 0),
            "display_h": getattr(self, "_display_h", 0),
        })

    def _load_tasks(self):
        from config import DISPLAY_PRESETS, FONT_SCALE
        from test_loader import load_test
        from project import detect_project

        data = self._task_store.load()
        if not data:
            return

        names         = data.get("tests", [])
        self._station = data.get("station", "")
        self._project = data.get("project", None)

        saved_preset = data.get("preset", "")
        if saved_preset and (saved_preset in DISPLAY_PRESETS or saved_preset == "Custom"):
            self._preset    = saved_preset
            self._scale     = FONT_SCALE.get(saved_preset, 1.0)
            self._display_w = data.get("display_w", self._display_w)
            self._display_h = data.get("display_h", self._display_h)

        for name in names:
            if name.startswith("flash:") and name.count(":") < 2:
                log.warning(
                    "Skip test format lama %r — pilih ulang Flash project via Add Test", name
                )
                continue
            try:
                item = load_test(name)
                self._tests.append(item)
                self._test_names.append(name)
            except Exception as e:
                log.warning("Gagal load test %r: %s", name, e)

        if not self._project:
            self._project = detect_project(self._test_names)

        if self._project == "tm81" or (self._project or "").startswith("tm81_"):
            self._keepalive.start()
