"""
commands/tm81/bl_goto_app.py — Bootloader → Lompat ke App (CMD BL 0x66)

Sebelum mengirim BL_GOTO_APP, script ini query OTA progress terlebih dahulu.
Jika image di flash belum lengkap (OTA terpotong di tengah), perintah jump
DITOLAK agar device tidak bootloop ke app yang tidak valid.
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

BOOT_REASON_NORMAL = 1
_NO_FRAME          = 0xFFFF
_CHUNK_SIZE        = 512


class BLGotoApp(TM81Command):

    def execute(self) -> str:
        # ── Jump gate ──────────────────────────────────────────────────────
        # Query OTA progress dulu. Kalau image belum selesai, tolak jump
        # agar device tidak bootloop ke app yang tidak valid.
        prog = self.xfer(CmdId.BL_GET_OTA_PROGRESS, timeout=2.0)
        if prog.valid and len(prog.payload) >= 10:
            p        = prog.payload
            dev_size = int.from_bytes(p[0:4], "little")
            dev_last = int.from_bytes(p[8:10], "little")

            if dev_size > 0 and dev_size < 0xFFFFFFFF and dev_last != _NO_FRAME:
                frames_needed  = (dev_size + _CHUNK_SIZE - 1) // _CHUNK_SIZE
                frames_written = dev_last + 1
                if frames_written < frames_needed:
                    msg = (
                        f"NG:REFUSE — OTA image belum selesai: "
                        f"frame {frames_written}/{frames_needed} ditulis "
                        f"(size={dev_size} B). "
                        f"Selesaikan upload dulu dengan BLWriteFirmware."
                    )
                    _log.warning("  [BLGotoApp] jump gate REFUSE: %s", msg)
                    return msg

            _log.debug("  [BLGotoApp] jump gate OK — image lengkap atau EEPROM bersih")
        else:
            _log.debug(
                "  [BLGotoApp] OTA progress tidak tersedia (%s) — "
                "bootloader lama? Lanjut, validasi tetap berlaku di device.",
                prog.error
            )

        # ── Kirim BL_GOTO_APP ─────────────────────────────────────────────
        data   = BOOT_REASON_NORMAL.to_bytes(1, "little")
        result = self.xfer(CmdId.BL_GOTO_APP, data=data, timeout=5.0)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  Bootloader → App OK")
        return "OK"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = BLGotoApp().execute()
    print(result)
    sm.disconnect_all()
