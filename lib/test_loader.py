"""
test_loader.py — Facade publik untuk semua test loaders.

Semua implementasi ada di loaders/:
  loaders/context.py  — shared context (device_id, dll.)
  loaders/base.py     — JsonTestSource base class
  loaders/flash.py    — flash loader
  loaders/voltage.py  — voltage loader
  loaders/tm81.py     — TM81 sources (auto-discovered dari commands/tm81/config/)
  loaders/bexa.py     — BexaTestSource

File ini menyediakan:
  discover_tests()  — scan folder tests/ untuk modul class-based/functional
  load_test(name)   — dispatcher ke loaders yang sesuai berdasarkan prefix
  Re-export simbol publik agar caller tidak perlu ubah import.
"""

import importlib
import inspect
import logging
import pkgutil
import tests

_log = logging.getLogger("test_loader")

from test_base    import TestBase
from test_modules import build_test_item

# ---------------------------------------------------------------------------
# Re-export simbol publik — hanya yang benar-benar dipakai dari luar
# ---------------------------------------------------------------------------

from loaders import (
    # context
    set_tk_root, watch_context, get_context, update_context,
    # flash
    flash_project_names, flash_project_label, flash_module_names,
    load_flash_tests_named, load_flash_tests, get_flash_sources,
    # voltage
    load_voltage_tests, voltage_module_names, get_voltage_sources,
    # tm81
    load_tm81_tests, tm81_module_names, tm81_label,
    get_tm81_extra_sources,
    # bexa
    load_bexa_tests, bexa_module_names, bexa_label,
)


# ---------------------------------------------------------------------------
# Helpers untuk discover/load test modul dari folder tests/
# ---------------------------------------------------------------------------

def _find_test_class(mod):
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, TestBase) and obj is not TestBase:
            return obj
    return None


def _make_item(cls_or_mod):
    title   = getattr(cls_or_mod, "TITLE",       "Unnamed")
    ttype   = getattr(cls_or_mod, "TYPE",         "auto").lower()
    cmd     = getattr(cls_or_mod, "COMMAND",      "UNKNOWN")
    desc    = getattr(cls_or_mod, "DESCRIPTION",  "")
    steps   = getattr(cls_or_mod, "STEPS",        5)
    step_ms = getattr(cls_or_mod, "STEP_MS",      300)

    if inspect.isclass(cls_or_mod):
        instance = cls_or_mod()
        run_fn   = instance.run if hasattr(instance, "run") else None
    else:
        raw_run = getattr(cls_or_mod, "run", None)
        run_fn  = raw_run if callable(raw_run) else None

    kw = dict(title=title, command=cmd, description=desc, run_fn=run_fn)
    if ttype == "progress":
        kw.update(steps=steps, step_ms=step_ms)
    return build_test_item(ttype, **kw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_tests():
    """Scan folder tests/ — skip file yang dihandle via loaders/."""
    _SKIP = {"flash_test", "voltage_test", "tm81_test", "bexa_test", "crc_comm_test"}
    results = []
    for _finder, name, _ in pkgutil.iter_modules(tests.__path__):
        if name in _SKIP:
            continue
        mod    = importlib.import_module(f"tests.{name}")
        cls    = _find_test_class(mod)
        target = cls if cls is not None else mod
        label  = getattr(target, "TITLE", name)
        results.append((name, label, target))
    results.sort(key=lambda x: x[1])
    return results


def load_test(module_name: str):
    """Load satu test dan kembalikan TestItem.

    Format:
        "tm81:<name>"         — tm81_test.json
        "tm81_ota:<name>"     — tm81_ota.json  (OTA, auto-discovered)
        "tm81_join:<name>"    — tm81_join.json (generic, auto-discovered)
        "voltage:<name>"      — voltage.json
        "flash:<proj>:<name>" — flash.json
        "bexa:<name>"         — bexa_test.json
        "<module>"            — tests/<module>.py
    """
    from loaders import load_tm81_test, _load_flash_by_name, _load_voltage_by_name, load_bexa_test

    if module_name.startswith("tm81:"):
        return load_tm81_test(module_name[5:])

    if module_name.startswith("voltage:"):
        return _load_voltage_by_name(module_name[8:])

    if module_name.startswith("flash:"):
        parts = module_name[6:].split(":", 1)
        if len(parts) != 2:
            raise KeyError(
                f"Format flash tidak valid: '{module_name}' "
                f"(harus 'flash:<proj>:<region>')"
            )
        return _load_flash_by_name(*parts)

    # Auto-dispatch ke semua TM81 sources (OTA, join, dll.)
    for src in get_tm81_extra_sources():
        pfx = f"{src.prefix}:"
        if module_name.startswith(pfx):
            return src.load_one(module_name[len(pfx):])

    if module_name.startswith("bexa:"):
        return load_bexa_test(module_name[5:])

    # Fallback: modul dari folder tests/
    mod = importlib.import_module(f"tests.{module_name}")
    cls = _find_test_class(mod)
    return _make_item(cls if cls is not None else mod)
