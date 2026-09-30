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
# Standalone — python tests/tm81_test.py [opsi] [nama_step ...]
#
#   python tests/tm81_test.py                        # suite tm81, semua step
#   python tests/tm81_test.py ping rtc_get           # suite tm81, step tertentu
#   python tests/tm81_test.py --suite tm81_ota       # suite lain
#   python tests/tm81_test.py --suite tm81_ota write_fw
#   python tests/tm81_test.py --list                 # daftar suite
#   python tests/tm81_test.py --suite tm81_ota --list  # daftar step di suite
#
# Suite dibaca lewat JsonTestSource, jadi format "tests" (lama) maupun
# "steps" (ringkas, merujuk _steps.json) dua-duanya jalan tanpa beda.
# =============================================================================

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "commands", "tm81", "config")
_STEPS_JSON = os.path.join(_CONFIG_DIR, "_steps.json")


def _all_sources() -> list:
    """Semua source TM81 aktif, lewat loaders.tm81 (BUKAN scan file sendiri) --
    ini satu-satunya cara yang otomatis benar utk ketiga mode suite: JSON
    biasa, JSON + .feature override urutan (replace-in-place), dan mode
    ringkas 1-file .feature saja / .feature + JSON pengaturan kecil (OTA).
    Lihat lib/loaders/tm81.py & lib/loaders/gherkin_lean.py."""
    from loaders.tm81 import get_tm81_extra_sources
    return get_tm81_extra_sources()


def _list_suites() -> list:
    """Nama (prefix) semua suite TM81 yang aktif, urut abjad."""
    return sorted(s.prefix for s in _all_sources())


def _make_source(suite: str):
    """Cari source TM81 aktif dengan prefix persis 'suite'. None kalau tidak ada."""
    for s in _all_sources():
        if s.prefix == suite:
            return s
    return None


def _resolve_suite(name: str) -> str:
    """Prefix TM81 sekarang selalu persis nama yang dipakai module_names()
    (mis. "tm81", "tm81_ota") -- tidak ada lagi alias nama-file vs
    "prefix"-di-JSON yang perlu di-resolve terpisah."""
    return name


def _main() -> int:
    import argparse
    import importlib

    ap = argparse.ArgumentParser(
        prog="tm81_test.py",
        description="Jalankan suite test TM81 dari terminal (tanpa GUI).")
    ap.add_argument("steps", nargs="*",
                    help="nama step yang dijalankan; kosong = semua")
    ap.add_argument("--suite", default="tm81",
                    help="nama suite (default: tm81 = tm81_test.json)")
    ap.add_argument("--list", action="store_true",
                    help="tampilkan daftar suite, atau daftar step bila --suite diberikan")
    ap.add_argument("--conn", default="ch340",
                    help="nama koneksi serial (default: ch340)")
    args = ap.parse_args()

    if args.list and args.suite == "tm81" and not any(
            a.startswith("--suite") for a in sys.argv[1:]):
        print("Suite tersedia:")
        for s in _list_suites():
            src = _make_source(s)
            n   = len(src.entries()) if src else 0
            print(f"  {s:22s} {n:2d} step")
        return 0

    suite = _resolve_suite(args.suite)
    src   = _make_source(suite)
    if src is None:
        print(f"NG: suite '{args.suite}' tidak ditemukan di {_CONFIG_DIR}")
        print("    pilihan:", ", ".join(_list_suites()) or "(kosong)")
        return 1

    entries = src.entries()
    if not entries:
        print(f"NG: suite '{suite}' tidak punya step")
        return 1

    if args.list:
        print(f"Step di {suite} ({len(entries)}):")
        for e in entries:
            mark = " [disabled]" if e.get("disabled") else ""
            print(f"  {e.get('name','?'):24s} {e.get('label','')}{mark}")
        return 0

    unknown = [n for n in args.steps if n not in {e.get("name") for e in entries}]
    if unknown:
        print(f"NG: step tidak ada di suite '{suite}': {', '.join(unknown)}")
        return 1

    import serial_manager as sm
    sm.connect(args.conn)

    passed = failed = skipped = 0
    print(f"Suite: {suite} ({len(entries)} step)\n")

    try:
        for entry in entries:
            name      = entry.get("name", "?")
            label     = entry.get("label", name)
            cls_path  = entry.get("command_class", "")

            if args.steps and name not in args.steps:
                continue
            if entry.get("disabled", False):
                print(f"  [SKIP] {label}")
                skipped += 1
                continue
            if not cls_path:
                print(f"  [SKIP] {label}: command_class kosong")
                skipped += 1
                continue

            mod_path, _, cls_name = cls_path.rpartition(".")
            try:
                cls    = getattr(importlib.import_module(mod_path), cls_name)
                params = entry.get("params", {})
                result = (cls(params=params) if params else cls()).execute()
            except Exception as e:
                result = f"NG:{e}"

            result = str(result)
            ok     = result.startswith("OK")
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {result.splitlines()[0]}")
            if ok: passed += 1
            else:  failed += 1
    finally:
        sm.disconnect_all()

    print(f"\nTotal: {passed} PASS, {failed} FAIL, {skipped} SKIP")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
