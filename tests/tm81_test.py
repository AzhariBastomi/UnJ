"""
tests/tm81_test.py — Single entry point untuk semua test TM81.

File ini menjadi satu-satunya program TM81. Di AddTestDialog akan muncul DUA grup:
  1. TM81 (N test)     — dibaca dari commands/tm81/config/tm81_test.json  → prefix "tm81:"
  2. TM81 Flash (4 step) — dibaca dari commands/tm81/config/tm81_ota.json → prefix "tm81_ota:"

TM81TestSource dan TM81OtaTestSource (lib/test_loader.py) masing-masing membuat
TestItem per entry, dengan run_fn yang memanggil command class dari commands/tm81/.

Format di tasks.json:
  "tm81:<name>"       misal: "tm81:get_version", "tm81:sensor_data"
  "tm81_ota:<name>" misal: "tm81_ota:write_fw", "tm81_ota:bl_goto_app"
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib
import json

from test_base import TestBase


# Ini dipakai discover_tests() untuk menemukan file ini
TITLE       = "TM81 Test"
TYPE        = "auto"
COMMAND     = "TM81"
DESCRIPTION = "Test suite untuk device TM81 (via IrDA/CH340)"


class TM81Test(TestBase):
    """Placeholder agar discover_tests() bisa menemukan modul ini."""
    TITLE       = "TM81 Test"
    TYPE        = "auto"
    COMMAND     = "TM81"
    DESCRIPTION = "Test suite untuk device TM81 (via IrDA/CH340)"


# =============================================================================
# Standalone — python tests/tm81_test.py [test_name ...]
#   python tests/tm81_test.py              # jalankan semua yang tidak disabled
#   python tests/tm81_test.py ping rtc_get # hanya test tertentu
# =============================================================================

if __name__ == "__main__":
    import importlib, json

    _here = os.path.dirname(os.path.abspath(__file__))
    _json_path = os.path.join(_here, "..", "commands", "tm81", "config", "tm81_test.json")
    if not os.path.exists(_json_path):
        print("NG: tm81_test.json tidak ditemukan"); sys.exit(1)

    _data    = json.load(open(_json_path, encoding="utf-8"))
    _tests   = _data.get("tests", [])
    _filter  = sys.argv[1:] if len(sys.argv) > 1 else []

    import serial_manager as sm
    sm.connect("ch340")

    _passed = _failed = _skipped = 0

    for _entry in _tests:
        _name    = _entry.get("name", "?")
        _label   = _entry.get("label", _name)
        _disabled = _entry.get("disabled", False)
        _cls_path = _entry.get("command_class", "")

        if _disabled:
            print(f"  [SKIP] {_label}")
            _skipped += 1
            continue

        if _filter and _name not in _filter:
            continue

        if not _cls_path:
            print(f"  [SKIP] {_label}: no command_class")
            _skipped += 1
            continue

        # Dynamic import: "commands.tm81.ping.Ping" -> module + class
        _mod_path, _, _cls_name = _cls_path.rpartition(".")
        try:
            _mod    = importlib.import_module(_mod_path)
            _cls    = getattr(_mod, _cls_name)
            _params = _entry.get("params", {})
            _cmd    = _cls(params=_params) if _params else _cls()
            _result = _cmd.execute()
        except Exception as _e:
            _result = f"NG:{_e}"

        _ok = _result.startswith("OK")
        _status = "PASS" if _ok else "FAIL"
        print(f"  [{_status}] {_label}: {_result}")
        if _ok: _passed += 1
        else:   _failed += 1

    print(f"\nTotal: {_passed} PASS, {_failed} FAIL, {_skipped} SKIP")
    sm.disconnect_all()
