"""
tests/bexa_test.py — Entry point untuk semua test BEXA.

Test dibaca dari commands/bexa/config/bexa_test.json.
Format module di tasks.json: "bexa:<name>"  misal "bexa:config_request"

Standalone:
    python tests/bexa_test.py                    # semua yang tidak disabled
    python tests/bexa_test.py tactile_read imu   # filter by name
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))

from test_base import TestBase


TITLE       = "BEXA Test"
TYPE        = "auto"
COMMAND     = "BEXA"
DESCRIPTION = "Test suite untuk device BEXA (via Bluetooth SPP)"


class BexaTest(TestBase):
    TITLE       = "BEXA Test"
    TYPE        = "auto"
    COMMAND     = "BEXA"
    DESCRIPTION = "Test suite untuk device BEXA (via Bluetooth SPP)"


# ─────────────────────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import importlib, os, sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _sys.path.insert(0, os.path.join(_here, "..", "lib"))
    # Lewat loaders.bexa (bukan baca bexa_test.json langsung) -- suite ini
    # sekarang bisa berupa bexa_test.json BIASA atau mode ringkas (cuma
    # commands/bexa/config/bexa_test.feature, tanpa JSON sama sekali).
    # Lihat lib/loaders/bexa.py & lib/loaders/gherkin_lean.py.
    from loaders.bexa import _active_bexa_source
    _tests  = _active_bexa_source.entries()
    _filter = sys.argv[1:] if len(sys.argv) > 1 else []

    import serial_manager as sm
    sm.connect("bluetooth")

    _passed = _failed = _skipped = 0

    for _entry in _tests:
        _name     = _entry.get("name", "?")
        _label    = _entry.get("label", _name)
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

        _mod_path, _, _cls_name = _cls_path.rpartition(".")
        try:
            _mod    = importlib.import_module(_mod_path)
            _cls    = getattr(_mod, _cls_name)
            _params = _entry.get("params", {})
            _cmd    = _cls(params=_params) if _params else _cls()
            _result = _cmd.execute()
        except Exception as _e:
            _result = f"NG:{_e}"

        _ok     = _result.startswith("OK")
        _status = "PASS" if _ok else "FAIL"
        print(f"  [{_status}] {_label}: {_result}")
        if _ok: _passed += 1
        else:   _failed += 1

    print(f"\nTotal: {_passed} PASS, {_failed} FAIL, {_skipped} SKIP")
    sm.disconnect_all()
