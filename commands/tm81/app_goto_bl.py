"""
commands/tm81/app_goto_bl.py — Reboot ke Bootloader (CMD 0x05)
Kirim dari App mode → masuk Bootloader mode (untuk OTA IrDA).
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

BOOT_REASON_IRDA_OTA = 2


class AppGotoBL(TM81Command):

    def execute(self) -> str:
        data   = BOOT_REASON_IRDA_OTA.to_bytes(1, "little")
        result = self.xfer(CmdId.USR_REBOOT_BOOTLOADER, data=data, timeout=5.0)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  App → Bootloader OK")
        return "OK"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = AppGotoBL().execute()
    print(result)
    sm.disconnect_all()
