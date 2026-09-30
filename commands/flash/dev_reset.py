"""
commands/flash/dev_reset.py — Reset device via ST-Link/STM32_Programmer_CLI

Reset "keras" lewat hardware debugger (bukan command serial TM81/BEXA) —
dipakai mis. buat verifikasi config yang tersimpan di EEPROM/Flash device
bertahan setelah device benar-benar direset, bukan cuma soft-reboot dari App.
Tinggal di commands/flash/ (bukan commands/tm81/) karena ini operasi
ST-Link/programmer, sama kelompoknya dengan flasher.py & stlink_path.py,
bukan protokol serial device tertentu — dipakai lintas suite (TM81, dst.)
lewat "command_class" di _steps.json.

Deteksi OS (Windows/Linux) & tool (STM32_Programmer_CLI / st-flash) otomatis
lewat lib/flasher.py:reset_device() -> lib/stlink_path.py:find_flash_tool()
(persis yang dipakai Stm32Flasher untuk flashing).

  Windows : STM32_Programmer_CLI.exe -c port=SWD -rst
  Linux   : st-flash reset
"""

import logging
_log = logging.getLogger(__name__)

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))

from flasher import reset_device


class DevReset:
    """Reset device lewat ST-Link/STM32_Programmer_CLI — bukan lewat serial."""

    def __init__(self, params=None, **_kwargs):
        pass

    def execute(self) -> str:
        result = reset_device()
        if not result.ok:
            return f"NG:{result.message}"
        _log.debug("  Reset device (ST-Link) OK")
        return "OK"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(DevReset().execute())
