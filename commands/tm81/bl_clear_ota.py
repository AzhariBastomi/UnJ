"""
commands/tm81/bl_clear_ota.py — Reset Metadata OTA di EEPROM (CMD BL 107)

Mengirim perintah BL_OTA_CLEAR ke bootloader untuk menghapus semua
metadata OTA yang tersimpan di EEPROM:
  - current_fw_size  → 0
  - current_fw_crc   → 0
  - last_frame_id    → 0xFFFF (NO_FRAME)

Berguna sebelum memulai fresh OTA transfer — pastikan tidak ada sisa
metadata dari sesi sebelumnya yang bisa menyebabkan resume ke CRC yang salah.
"""

import logging
_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class BLClearOta(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.BL_OTA_CLEAR, timeout=3.0)
        if not result.valid and result.error not in ("ACK",):
            _log.warning("  BL_OTA_CLEAR NG: %s", result.error)
            return f"NG:{result.error}"
        _log.debug("  BL_OTA_CLEAR → ACK (EEPROM metadata cleared)")
        return "OK"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = BLClearOta().execute()
    print(result)
    sm.disconnect_all()
