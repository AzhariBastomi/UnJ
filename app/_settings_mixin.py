"""SettingsMixin — dialog settings dan dynamic buttons di header."""

import os, importlib, logging
import tkinter as tk

from config import BASE_FONTS, COLORS

log = logging.getLogger("main")


class SettingsMixin:

    # ------------------------------------------------------------------
    # Display settings
    # ------------------------------------------------------------------

    def _open_display_settings(self):
        from ui.dialogs import DisplaySettingsDialog
        DisplaySettingsDialog(self, self._preset, on_apply=self._apply_display)

    def _apply_display(self, preset: str, width: int, height: int):
        self._preset    = preset
        self._scale     = importlib.import_module("config").FONT_SCALE.get(preset, 1.0)
        self._display_w = width
        self._display_h = height
        self.geometry(f"{width}x{height}")
        self.resizable(preset == "Custom", preset == "Custom")
        self._save_tasks()
        for child in self.winfo_children():
            child.destroy()
        self._build()
        self._list_panel.load_tests(self._tests)
        self._update_debug_btn()

    # ------------------------------------------------------------------
    # Generic on-save handler — dipanggil setelah dialog settings apapun
    # ------------------------------------------------------------------

    def _on_any_dialog_saved(self):
        """Satu callback untuk semua dialog settings.

        Urutan:
          1. Invalidate cache fw (untuk OTA)
          2. Reload semua test items dari file config masing-masing
          3. Refresh validasi tiap row (untuk Commissioning dll)
          4. Update tombol Start enable/disable
        """
        self.invalidate_fw_cache()
        self._reload_all_tests()
        if hasattr(self, "_list_panel"):
            self._list_panel.refresh_validations()
        self._update_start_btn()

    def _reload_all_tests(self):
        """Load ulang semua test items dari file config masing-masing."""
        from test_loader import load_test
        changed = False
        for i, name in enumerate(self._test_names):
            try:
                self._tests[i] = load_test(name)
                changed = True
            except Exception as e:
                log.warning("Gagal reload test %r: %s", name, e)
        if changed and hasattr(self, "_list_panel"):
            self._list_panel.load_tests(self._tests)

    # ------------------------------------------------------------------
    # Extra-kwargs helpers (dipanggil oleh _refresh_dynamic_buttons)
    # ------------------------------------------------------------------

    def _get_active_flash_project(self) -> str:
        for name in self._test_names:
            if name.startswith("flash:"):
                parts = name[len("flash:"):].split(":", 1)
                if len(parts) == 2:
                    return parts[0]
        return ""

    def _get_flash_dialog_kwargs(self) -> dict:
        proj = self._get_active_flash_project()
        from loaders.flash import get_flash_sources
        for src in get_flash_sources():
            if src._proj_name == proj:
                return {"json_path": src.json_path}
        return {}

    def _get_ota_dialog_kwargs(self) -> dict:
        _cfg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "commands", "tm81", "config")
        active_json = None
        for p in ("tm81_ota:", "tm81_ota2:", "tm81_ota_bl:"):
            prefix_key = p.rstrip(":")
            if any(n.startswith(p) for n in self._test_names):
                try:
                    from loaders.tm81 import get_ota_json_path
                    active_json = get_ota_json_path(prefix_key)
                except Exception:
                    pass
                if not active_json:
                    candidate = os.path.join(_cfg_dir, f"{prefix_key}.json")
                    if os.path.isfile(candidate):
                        active_json = candidate
                break
        return {"json_path": active_json} if active_json else {}

    # ------------------------------------------------------------------
    # Dynamic buttons — data-driven via _btn_registry
    # ------------------------------------------------------------------

    def _refresh_dynamic_buttons(self):
        from app._btn_registry import get_all

        for w in self._dyn_btns.winfo_children():
            w.destroy()

        fs = lambda k: max(7, int(BASE_FONTS[k] * self._scale))
        has_any = False

        for spec in get_all():
            matched = any(
                any(n.startswith(p) for p in spec.prefixes)
                and not any(n.startswith(e) for e in spec.excludes)
                for n in self._test_names
            )
            if not matched:
                continue

            tk.Button(
                self._dyn_btns, text=spec.label,
                command=self._make_btn_opener(spec),
                bg=COLORS["header_bg"], fg="#f39c12", relief="flat",
                font=("TkDefaultFont", fs("button")), cursor="hand2",
            ).pack(side="right", padx=6)
            has_any = True

        if has_any:
            if not self._dyn_btns.winfo_ismapped():
                self._dyn_btns.pack(side="right", before=self._display_btn)
        else:
            self._dyn_btns.pack_forget()

    def _make_btn_opener(self, spec):
        """Buat fungsi opener untuk satu ButtonSpec (closure-safe)."""
        def _opener():
            mod_path, cls_name = spec.dialog.rsplit(".", 1)
            DialogClass = getattr(importlib.import_module(mod_path), cls_name)

            on_save = None
            if spec.on_save_attr:
                obj = self
                for attr in spec.on_save_attr.split("."):
                    obj = getattr(obj, attr)
                on_save = obj

            kwargs = dict(spec.static_kwargs or {})
            if spec.kwargs_method:
                kwargs.update(getattr(self, spec.kwargs_method)())
            if on_save:
                kwargs["on_save"] = on_save

            DialogClass(self, **kwargs)
        return _opener
