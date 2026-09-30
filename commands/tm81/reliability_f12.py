"""
commands/tm81/reliability_f12.py — Test F12: slot history basi (hari-1 terlewat)

NON-destructive ke firmware (menulis EEPROM history slot 2, byte 256-383).

Metadata bulan hanya ditulis saat day==1 (calestek_history.c:76). Juni & September
berbagi slot 2 karena (month-1)%3 sama. Menulis September mulai hari-2 mengisi data
tanpa update metadata (masih "Juni") → baca September ditolak.

Alur:
  1. Tulis Juni hari-1  (01 06 1a 6f000000)  -> ACK, slot2 metadata = Juni
  2. Tulis Sept hari-2  (02 09 1a de000000)  -> ACK, data masuk, metadata TETAP Juni
  3. Baca Sept hari-2   (02 09 1a)           -> NAK  = BUG

Verdict:
  - Langkah 3 NAK  => BUG F12 TERBUKTI (data ada tapi dibaca ditolak).
  - Langkah 3 ACK/data => tidak terbukti (sudah dipatch / metadata ditulis benar).

Referensi: firmware calestek_history.c:70-89,113-123. SWM reliability review F12.
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

# day, month, year(=2000+0x1a=2026), value(u32 LE)
_JUNE_D1  = bytes([1, 6, 26]) + (111).to_bytes(4, "little")   # 01 06 1a 6f000000
_SEPT_D2  = bytes([2, 9, 26]) + (222).to_bytes(4, "little")   # 02 09 1a de000000
_READ_SEP = bytes([2, 9, 26])                                  # 02 09 1a


class ReliabilityF12(TM81Command):

    def execute(self) -> str:
        # 1. Juni hari-1 → set metadata slot2 = Juni
        r = self.xfer(CmdId.USAGE_HISTORY_WRITE, _JUNE_D1, retries=3)
        if not r.valid and r.error != "ACK":
            return f"NG:tulis Juni-1 gagal ({r.error})"

        # 2. Sept hari-2 → data masuk, metadata tidak di-update
        r = self.xfer(CmdId.USAGE_HISTORY_WRITE, _SEPT_D2, retries=3)
        if not r.valid and r.error != "ACK":
            return f"NG:tulis Sept-2 gagal ({r.error})"

        # 3. Baca Sept hari-2
        r = self.xfer(CmdId.USAGE_HISTORY_READ, _READ_SEP, retries=3)

        if not r.valid and r.error == "NAK":
            return ("OK:BUG F12 TERBUKTI — baca September hari-2 di-NAK padahal "
                    "data sudah ditulis (metadata slot masih 'Juni').")
        if r.valid:
            val = int.from_bytes(r.payload[:4], "little") if len(r.payload) >= 4 else None
            return (f"OK:TIDAK terbukti — baca September berhasil (nilai={val}). "
                    f"Metadata tampak ditulis benar / sudah dipatch.")
        return f"NG:hasil baca tak terduga ({r.error})"


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    print(ReliabilityF12().execute())
    sm.disconnect_all()
