"""
voltage_test.py - Manual voltage test, satu instance per entry di voltage.json.

Operator cek tegangan pakai multimeter, lalu klik OK/NG.
CLI:
    python voltage_test.py 3v3
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from test_base import TestBase

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_voltage_entries() -> list:
    """Semua titik ukur voltage lewat loaders.voltage (BUKAN scan *.json
    sendiri) -- daftarnya sekarang dari voltage.feature + _steps.json, lihat
    lib/loaders/voltage.py."""
    import sys as _s
    _lib = os.path.join(_ROOT, "lib")
    if _lib not in _s.path: _s.path.insert(0, _lib)
    from loaders.voltage import get_voltage_sources
    return [
        {"name": s._name, "label": s._label, "command": s._command,
         "description": s._desc}
        for s in get_voltage_sources()
    ]


class VoltageTest(TestBase):
    TITLE       = "Voltage"
    TYPE        = "manual"
    COMMAND     = "VOLT"
    DESCRIPTION = ""

    # Di-set oleh factory
    ENTRY: dict = {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    entry_name = sys.argv[1] if len(sys.argv) > 1 else None
    if not entry_name:
        print("Usage: python voltage_test.py <name>  (misal: 3v3, 1v8)")
        sys.exit(1)

    entries = _load_voltage_entries()
    entry = next((v for v in entries if v.get("name") == entry_name), None)
    if not entry:
        names = [v.get("name") for v in entries]
        print(f"Entry {entry_name!r} tidak ditemukan. Tersedia: {names}")
        sys.exit(1)

    label    = entry.get("label", entry_name)
    expected = entry.get("expected", "")
    tolerance = entry.get("tolerance", "")

    print(f"\n[Voltage] {label}")
    if expected:
        tol_str = f" ± {tolerance}" if tolerance else ""
        print(f"  Expected : {expected}{tol_str}")
    print(f"  Ukur tegangan dengan multimeter, lalu konfirmasi.")
    print()

    while True:
        ans = input("  Hasil? [o=OK / n=NG / s=Skip]: ").strip().lower()
        if ans in ("o", "ok", ""):
            print(f"  [PASS] {label}")
            break
        elif ans in ("n", "ng"):
            reason = input("  Alasan NG (opsional): ").strip()
            print(f"  [FAIL] {label}" + (f": {reason}" if reason else ""))
            break
        elif ans in ("s", "skip"):
            print(f"  [SKIP] {label}")
            break
        else:
            print("  Ketik o (OK), n (NG), atau s (Skip)")
