"""
commands/tm81/reliability_f10.py — Test F10: panjang respons harian/bulanan tertukar

NON-destructive selain menulis satu bulan history (slot September) sebagai seed.

scp.c:1131-1136: permintaan BULANAN (day=0) malah mengirim 4 byte, permintaan
HARIAN (day!=0) mengirim 124 byte — terbalik. Yang benar: bulanan 124, harian 4.

Alur:
  1. Seed September   : usage_history_write day=0 + 124 byte  -> ACK
  2. Baca BULANAN     : usage_history_read  day=0 (00 09 1a)  -> panjang payload?
  3. Baca HARIAN      : usage_history_read  day=1 (01 09 1a)  -> panjang payload?

Verdict (berdasar panjang payload respons):
  - bulanan=4  DAN harian=124  => BUG F10 TERBUKTI (tertukar).
  - bulanan=124 DAN harian=4   => benar (sudah dipatch).
  - selain itu                 => ambigu (lihat log).

Catatan: bergantung parser JIG mengembalikan payload apa adanya untuk panjang
tak biasa. Kalau salah satu baca ter-NAK, seed mungkin gagal — ulangi.
Referensi: firmware calestek_scp.c:1112-1138. SWM reliability review F10.
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

# Seed monthly: day=0, month=9, year=26, + 124 byte data (31 hari x 4). Aman:
# data_len firmware = 124 = HISTORY_MONTH_BUFFER_SIZE (tidak overflow spt F02).
_SEED = bytes([0, 9, 26]) + b"".join(
    (1000 + i).to_bytes(4, "little") for i in range(31)
)
_READ_MONTH = bytes([0, 9, 26])   # day=0 → bulanan
_READ_DAY   = bytes([1, 9, 26])   # day=1 → harian


class ReliabilityF10(TM81Command):

    def execute(self) -> str:
        # 1. Seed satu bulan
        r = self.xfer(CmdId.USAGE_HISTORY_WRITE, _SEED, retries=3)
        if not r.valid and r.error != "ACK":
            return f"NG:seed September gagal ({r.error})"

        # 2. Baca bulanan (day=0)
        rm = self.xfer(CmdId.USAGE_HISTORY_READ, _READ_MONTH, retries=3)
        if not rm.valid:
            return f"NG:baca bulanan gagal ({rm.error})"
        month_len = len(rm.payload)

        # 3. Baca harian (day=1)
        rd = self.xfer(CmdId.USAGE_HISTORY_READ, _READ_DAY, retries=3)
        if not rd.valid:
            return f"NG:baca harian gagal ({rd.error})"
        day_len = len(rd.payload)

        _log.debug("payload bulanan=%dB, harian=%dB", month_len, day_len)

        if month_len == 4 and day_len == 124:
            return (f"OK:BUG F10 TERBUKTI — panjang tertukar "
                    f"(bulanan={month_len}B, harian={day_len}B; seharusnya 124 & 4).")
        if month_len == 124 and day_len == 4:
            return (f"OK:TIDAK terbukti — panjang benar "
                    f"(bulanan={month_len}B, harian={day_len}B). Sudah dipatch.")
        return (f"NG:hasil ambigu — bulanan={month_len}B, harian={day_len}B "
                f"(cek log / firmware).")


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    print(ReliabilityF10().execute())
    sm.disconnect_all()
