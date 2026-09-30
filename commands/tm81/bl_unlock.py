"""
commands/tm81/bl_unlock.py — BL-Override Unlock (5-Knock Mechanism)

Untuk OTA ke region Bootloader dari App yang sedang running, firmware memiliki
guard yang memerlukan BL_GOTO_APP (cmd 102) dikirim 5 kali berturut-turut.
Semua knock akan NAK selama locked — ini NORMAL dan bukan error.

Setelah 5 knock NAK selesai, OTA ke region Bootloader diizinkan hingga
reboot berikutnya (runtime-only, setiap reboot mengunci ulang).

PENTING:
- Jika salah satu knock mendapat ACK: device BUKAN app berguard
  (sudah di bootloader atau app lama tanpa guard). ABORT.
- Jangan reboot antara unlock dan BLWriteFirmware (region BL).
- Unlock ini hanya dibutuhkan untuk OTA Bootloader (device di App).
  OTA App (device di Bootloader) tidak memerlukan unlock.

Referensi: SWM_Test_Scripts/Src/OtaUnlockBl.py
"""

import logging
import time

_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

UNLOCK_REQ      = 5
BOOT_REASON_NORMAL = 1
KNOCK_DELAY_S   = 0.2


class BLUnlock(TM81Command):
    """
    Kirim BL_GOTO_APP (cmd 102) sebanyak 5 kali untuk membuka guard
    OTA ke region Bootloader.

    Semua knock diharapkan NAK — itu tanda guard sedang aktif dan
    knock berhasil dihitung oleh firmware. Jika ada yang ACK, abort.
    """

    RETRIES = 1   # tiap knock dihitung firmware; jangan dobel

    def execute(self) -> str:
        _log.debug(
            "  [BLUnlock] Memulai unlock sequence (%d knock, "
            "semua NAK = normal)",
            UNLOCK_REQ,
        )

        data = BOOT_REASON_NORMAL.to_bytes(1, "little")

        for attempt in range(1, UNLOCK_REQ + 1):
            result = self.xfer(CmdId.BL_GOTO_APP, data=data, timeout=3.0)

            got_ack = (result.error == "ACK")

            if got_ack:
                msg = (
                    f"NG:ABORT — knock {attempt}/{UNLOCK_REQ} mendapat ACK. "
                    "Device bukan app berguard: mungkin sudah di Bootloader "
                    "(cmd 102 langsung jump) atau app versi lama tanpa guard. "
                    "Jangan lanjutkan BL OTA di sini."
                )
                _log.warning("  [BLUnlock] %s", msg)
                return msg

            _log.debug(
                "  [BLUnlock] knock %d/%d: NAK (%s) — normal, lanjut",
                attempt, UNLOCK_REQ, result.error,
            )

            if attempt < UNLOCK_REQ:
                time.sleep(KNOCK_DELAY_S)

        _log.debug(
            "  [BLUnlock] Unlock selesai — %d knock NAK. "
            "BL-region OTA aktif hingga reboot berikutnya.",
            UNLOCK_REQ,
        )
        return "OK"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = BLUnlock().execute()
    print(result)
    sm.disconnect_all()
