"""TestMgmtMixin — add / reload / clear test items."""

import os, logging

from config import COLORS
# Dialog pesan sendiri, bukan messagebox bawaan Tk: yang bawaan tidak melewati
# TouchPopupMixin (tanpa wait_visibility + lift + focus_force + grab_set),
# sehingga di layar sentuh tap PERTAMA pada tombolnya ditelan window manager
# untuk keperluan focus/raise dan Clear baru jalan pada tap kedua.
# Lihat ui/dialogs/confirm.py.
from ui.dialogs.confirm import ask_yes_no, show_warning

log = logging.getLogger("main")


class TestMgmtMixin:

    def _open_add_test(self):
        from ui.dialogs import AddTestDialog
        AddTestDialog(
            self,
            on_add=self._add_test,
            on_add_batch=self._add_test_batch,
            current_project=self._project,
        )

    def _add_test(self, item, module_name: str = "", _refresh: bool = True):
        from project import module_project
        new_proj = module_project(module_name)
        if new_proj and self._project and new_proj != self._project:
            show_warning(
                self,
                "Konflik Project",
                f"Project aktif: {self._project.upper()}\n"
                f"Tidak bisa menambahkan modul project {new_proj.upper()}.\n"
                f"Hapus semua test {self._project.upper()} terlebih dahulu.",
            )
            return

        self._tests.append(item)
        self._test_names.append(module_name)

        if new_proj and self._project != new_proj:
            self._project = new_proj
            self._refresh_project_label()
            if new_proj == "tm81" or new_proj.startswith("tm81_"):
                self._keepalive.start()
            else:
                self._keepalive.stop()
                self._ka_led.config(fg=COLORS.get("border", "#444"))

        self._list_panel.append_row(item)
        if _refresh:
            self._list_panel.refresh_validations()
            self._refresh_dynamic_buttons()
            self._update_start_btn()
            self._save_tasks()

    def _add_test_batch(self, items_and_names: list):
        for item, name in items_and_names:
            self._add_test(item, name, _refresh=False)
        if hasattr(self, "_list_panel"):
            self._list_panel.refresh_validations()
        self._refresh_dynamic_buttons()
        self._update_start_btn()
        self._save_tasks()

    def _reset_project_config(self, project: str):
        """Reset field user-configurable di JSON sesuai project yang di-clear."""
        import json as _json
        _ROOT = os.path.dirname(os.path.abspath(__file__))

        try:
            if project == "flash":
                path       = os.path.join(_ROOT, "..", "config", "flash.json")
                flash_proj = self._get_active_flash_project()
                with open(path, encoding="utf-8") as f:
                    data = _json.load(f)
                regions = data.get("projects", {}).get(flash_proj, {}).get("regions", [])
                for region in regions:
                    region["file"] = ""
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, indent=2, ensure_ascii=False)
                log.info("[clear] flash.json[%s]: semua field 'file' direset", flash_proj)

            elif any(project == p.rstrip(":") for p in ("tm81_ota:", "tm81_ota2:", "tm81_ota_bl:")):
                path = os.path.join(_ROOT, "..", "commands", "tm81", "config",
                                    f"{project}.json")
                with open(path, encoding="utf-8") as f:
                    data = _json.load(f)
                data["fw_version"] = ""
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, indent=2, ensure_ascii=False)
                log.info("[clear] %s.json: fw_version direset", project)

        except Exception as e:
            log.warning("[clear] Gagal reset config '%s': %s", project, e)

    def _clear_all(self):
        if not self._tests:
            return
        if ask_yes_no(self, "Clear All", "Hapus semua test dari list?"):
            self._reset_project_config(self._project or "")
            self._tests.clear()
            self._test_names.clear()
            self._project = None
            self._keepalive.stop()
            self._refresh_project_label()
            self._refresh_dynamic_buttons()
            self._list_panel.load_tests(self._tests)
            self._update_start_btn()
            self._save_tasks()
            self._status_var.set("Ready")
