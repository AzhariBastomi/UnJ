"""
commands/tm81/bl_prepare.py — Persiapan Bootloader sebelum transfer firmware (BL_SET_RDY)

Step 2 dari OTA Flash sequence:
  1. AppGotoBL       — reboot ke BL
  2. BLPrepare       ← ini: kirim fw_size + CRC ke BL agar BL siap terima data
  3. BLWriteFirmware — kirim chunk firmware (BL_FW_DATA)
  4. BLGotoApp       — lompat ke App

Params (dari test_loader / params dict):
    fw_path  : path ke file firmware (.bin) — wajib

Referensi: tm81-command-tester/Src/BLPrepare.py
"""

import logging
_log = logging.getLogger(__name__)

import logging
import os
import time
from crccheck.crc import Crc32Mpeg2

_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

# Batas maksimum ukuran firmware App (sama dengan referensi AppConstants.FW_APP_MAX_SIZE)
APP_MAX_SIZE = 1024 * 160   # 160 KB


class BLPrepare(TM81Command):
    """
    Kirim BL_SET_RDY — beritahu bootloader ukuran firmware dan CRC32MPEG2.
    Setelah ACK diterima, tunggu 1 detik agar BL siap menerima chunk data.

    Harus dipanggil setelah AppGotoBL (+ jeda boot) dan sebelum BLWriteFirmware.
    """

    # Jeda setelah BL_SET_RDY ACK sebelum mulai kirim chunk (referensi: sleep(1))
    POST_SET_RDY_WAIT_S = 1.0

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._fw_path = p.get("fw_path", "")

    def execute(self) -> str:
        if not self._fw_path or not os.path.isfile(self._fw_path):
            return f"NG:File tidak ditemukan: {self._fw_path!r}"

        # Baca firmware (maks APP_MAX_SIZE) — hitung ukuran dan CRC
        with open(self._fw_path, "rb") as f:
            fw_data = f.read(APP_MAX_SIZE)

        fw_size   = len(fw_data)
        crc_bytes = Crc32Mpeg2.calc(fw_data).to_bytes(4, "little")

        _log.debug("  BLPrepare: file=%s  size=%d B  CRC=%s",
                   os.path.basename(self._fw_path), fw_size, crc_bytes.hex(" "))

        # BL_SET_RDY payload: fw_size (4B LE) + CRC32MPEG2 (4B LE)
        payload = fw_size.to_bytes(4, "little") + crc_bytes
        result  = self.xfer(CmdId.BL_SET_RDY, payload, timeout=8.0)

        if not result.valid and result.error not in ("ACK",):
            return f"NG:BL_SET_RDY {result.error}"

        _log.debug("  BL_SET_RDY → ACK — tunggu %.1f s sebelum transfer ...",
                   self.POST_SET_RDY_WAIT_S)
        time.sleep(self.POST_SET_RDY_WAIT_S)

        return "OK"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    fw_path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not fw_path:
        print("Usage: python bl_prepare.py <fw_path>"); sys.exit(1)

    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = BLPrepare(params={"fw_path": fw_path}).execute()
    print(result)
    sm.disconnect_all()
