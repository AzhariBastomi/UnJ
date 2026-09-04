"""
flash_test.py - Generic flash test, satu instance per region di flash.json.

Tidak dipakai langsung — dibuat oleh test_loader via "flash:<name>" format.
Bisa juga diinstansiasi manual untuk CLI:
    python flash_test.py boot
    python flash_test.py app
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import json
from test_base import TestBase
from flasher import Stm32Flasher, Stm32Config
from stlink_path import find_flash_tool

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_flash_json(proj_name: str = "") -> dict:
    """Deprecated: load dari commands/flash/config/<proj>.json."""
    import sys as _s
    _lib = os.path.join(_ROOT, "lib")
    if _lib not in _s.path: _s.path.insert(0, _lib)
    from loaders.flash import get_flash_sources
    for src in get_flash_sources():
        if not proj_name or src._proj_name == proj_name:
            return src.read_json()
    return {}


class FlashTest(TestBase):
    """
    Base class flash test. Instance per region dibuat via factory.
    Jangan pakai langsung — set REGION dulu atau pakai for_region().
    """
    TITLE       = "Flash"
    TYPE        = "progress"
    COMMAND     = "FLASH"
    DESCRIPTION = ""
    STEPS       = 10
    STEP_MS     = 300

    # Di-set oleh factory (dict dari flash.json regions[i])
    REGION: dict = {}

    def run(self) -> str:
        region = self.REGION
        if not region:
            return "NG:Region tidak dikonfigurasi"

        try:
            tool = find_flash_tool()
        except FileNotFoundError as e:
            return f"NG:{e}"

        # flash_dir disuntik oleh FlashTestSource via key '_flash_dir' di REGION
        flash_dir = os.path.join(_ROOT, region.get("_flash_dir", "firmware"))

        # Baca file & address langsung dari region (single source of truth)
        fw_file = region.get("file", "").strip()
        address = region.get("address", "0x08000000").strip()

        if not fw_file:
            return f"NG:field 'file' kosong untuk region '{region.get('name', '?')}'"

        # Jika path absolut (dari Browse), pakai langsung; jika relatif, gabung flash_dir
        fw_path = fw_file if os.path.isabs(fw_file) else os.path.join(flash_dir, fw_file)
        if not os.path.isfile(fw_path):
            return f"NG:file tidak ada: {fw_path}"
        reset   = region.get("reset", True)
        cfg     = Stm32Config(stlink_bin=tool, flash_addr=address, reset=reset)
        result  = Stm32Flasher(cfg).flash(fw_path, progress_cb=self.report_progress)

        return "OK" if result.ok else f"NG:{result.message}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Usage:
    #   python flash_test.py <region>           — cari region di semua project
    #   python flash_test.py <proj> <region>    — project + region spesifik
    if len(sys.argv) == 3:
        proj_name, region_name = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        proj_name, region_name = None, sys.argv[1]
    else:
        print("Usage: python flash_test.py <region>")
        print("       python flash_test.py <proj> <region>  (misal: tm81 boot)")
        sys.exit(1)

    data = _load_flash_json(proj_name or "")
    if not data:
        print(f"Project {proj_name!r} tidak ditemukan di commands/flash/config/")
        sys.exit(1)

    flash_dir = data.get("flash_dir", "firmware")
    region = next((r for r in data.get("tests", []) if r.get("name") == region_name), None)
    if not region:
        names = [r.get("name") for r in data.get("tests", [])]
        print(f"Region {region_name!r} tidak ditemukan. Tersedia: {names}")
        sys.exit(1)

    # Inject _flash_dir agar FlashTest.run() tahu lokasi firmware
    region = {**region, "_flash_dir": flash_dir}

    cls      = type("_FlashTest", (FlashTest,), {"REGION": region})
    instance = cls()
    instance.set_progress_cb(lambda p: print(f"  Progress: {p:.0f}%", end="\r"))

    print(f"Flash region '{region_name}' @ {region.get('address')} ...")
    result = instance.run()
    print(f"\n[Flash {region_name}] -> {result}")
