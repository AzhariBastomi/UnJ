"""
loaders/flash.py — Flash test loader.

Auto-discover dari commands/flash/config/*.json.
Satu file JSON = satu FlashTestSource = satu project flash.
Format JSON: "tests" list (sama seperti TM81/BEXA), tiap entry = satu region flash.
"""

import logging
import os

from test_modules import ProgressBarTest
from loaders.base import JsonTestSource, _ROOT

_log       = logging.getLogger(__name__)
_FLASH_DIR = os.path.join(_ROOT, "commands", "flash", "config")


class FlashTestSource(JsonTestSource):
    """Satu flash JSON = satu project dengan N test entries (regions)."""

    entity_label = "Flash region"

    def __init__(self, json_path: str):
        self.json_path  = json_path
        data            = self.read_json()
        stem            = os.path.splitext(os.path.basename(json_path))[0]
        self._proj_name = stem
        self._label     = data.get("label", stem.upper())
        # prefix dari JSON (mis. "flash:tm81") → module names: "flash:tm81:boot"
        self.prefix     = data.get("prefix", f"flash:{stem}")

    def label(self) -> str:
        return self._label

    def make_item(self, entry: dict) -> ProgressBarTest:
        from loaders.base import _ROOT as ROOT
        name      = entry.get("name", "unknown")
        label     = entry.get("label", name)
        desc      = entry.get("description", f"Flash {label}")
        address   = entry.get("address", "0x08000000").strip()
        fw_file   = entry.get("file", "").strip()
        fw_label  = os.path.basename(fw_file) if fw_file else "⚠ file belum diset"
        full_desc = f"{desc}  •  {fw_label}  @  {address}"
        cmd_tag   = f"{self._proj_name.upper()}_{name.upper()}"

        cls_path  = entry.get("command_class", "tests.flash_test.FlashTest")
        FlashCls, err = self.resolve_command_class(cls_path)

        # TestController memanggil set_progress_cb() SEBELUM run_fn() dijalankan,
        # sedangkan instance FlashTest baru dibuat di dalam _run_fn(). Simpan
        # callback-nya di sini supaya bisa di-inject saat instance dibuat.
        _cb_holder = {"cb": None}

        def _set_progress_cb(cb):
            _cb_holder["cb"] = cb

        def _run_fn():
            if FlashCls is None:
                return f"NG:{err or 'command_class tidak ditemukan'}"
            try:
                inst = type(
                    f"_FlashTest_{self._proj_name}_{name}", (FlashCls,), {
                        "TITLE":       f"Flash {label}",
                        "COMMAND":     f"FLASH_{cmd_tag}",
                        "DESCRIPTION": full_desc,
                        "REGION":      entry,
                    }
                )()
                if _cb_holder["cb"] is not None:
                    inst.set_progress_cb(_cb_holder["cb"])
                return inst.run()
            except Exception as e:
                _log.exception("[Flash] %s exception:", label)
                return f"NG:{e}"

        # run_fn adalah closure (tidak punya __self__), jadi tempelkan setter-nya
        # sebagai atribut fungsi agar TestController bisa menemukannya.
        _run_fn.set_progress_cb = _set_progress_cb

        return ProgressBarTest(
            title       = f"Flash {label}",
            command     = f"FLASH_{cmd_tag}",
            description = full_desc,
            run_fn      = _run_fn,
            steps       = entry.get("steps",   10),
            step_ms     = entry.get("step_ms", 300),
        )


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

def _scan_flash_sources() -> list[FlashTestSource]:
    sources = []
    try:
        for fname in sorted(os.listdir(_FLASH_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(_FLASH_DIR, fname)
            try:
                sources.append(FlashTestSource(path))
            except Exception as exc:
                _log.warning("Gagal load flash config %s: %s", fname, exc)
    except FileNotFoundError:
        _log.warning("Folder flash config tidak ditemukan: %s", _FLASH_DIR)
    return sources


_flash_sources: list[FlashTestSource] = _scan_flash_sources()


def reload_flash_sources() -> None:
    global _flash_sources
    _flash_sources = _scan_flash_sources()


def get_flash_sources() -> list[FlashTestSource]:
    return list(_flash_sources)


def _get_source(proj_name: str) -> "FlashTestSource | None":
    for src in _flash_sources:
        if src._proj_name == proj_name:
            return src
    return None


# ---------------------------------------------------------------------------
# Public API — kompatibel dengan __init__.py / test_loader.py / add_test.py
# ---------------------------------------------------------------------------

def flash_project_names() -> list[str]:
    return [s._proj_name for s in _flash_sources]


def flash_project_label(proj_name: str) -> str:
    src = _get_source(proj_name)
    return src._label if src else proj_name.upper()


def flash_module_names(proj_name: str) -> list[str]:
    src = _get_source(proj_name)
    return src.module_names() if src else []


def load_flash_tests_named(proj_name: str) -> list[tuple]:
    src = _get_source(proj_name)
    if src is None:
        return []
    return list(zip(src.load_all(), src.module_names()))


def load_flash_tests(proj_name: str) -> list:
    return [item for item, _ in load_flash_tests_named(proj_name)]


def _load_flash_by_name(proj_name: str, region_name: str) -> ProgressBarTest:
    src = _get_source(proj_name)
    if src is None:
        raise KeyError(f"Flash project '{proj_name}' tidak ditemukan di {_FLASH_DIR}")
    return src.load_one(region_name)


def _read_flash_json() -> dict:
    """Deprecated: baca JSON project pertama (backward compat)."""
    return _flash_sources[0].read_json() if _flash_sources else {}
