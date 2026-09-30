"""
commands/tm81/reliability_f07.py — Test F07: konversi tahun RTC / alarm harian gagal

NON-destructive. Butuh log APP_LOG device via ST-Link VCP (koneksi 'stlink').

F07: writer RTC menyimpan tm_year (basis-1900, mis. 126) langsung ke field year
RTC, sedangkan scheduler `rtc_to_struct_tm` menambah +100 lagi → tahun jadi 2126.
Untuk periode HARIAN (set_daily_alarm) tahun itu masuk mktime; kalau time_t 32-bit,
2126 melewati 2038 → mktime overflow → `[E] mktime.` (scheduler.c:151) → alarm
harian gagal dijadwalkan.

Trigger:
  1. Set config submit_id=5 (1day)  -> periode harian pakai set_daily_alarm
  2. Set RTC (rtc_set via CMD 0x0B)  -> RTC terisi tahun berjalan
  3. Force send (CMD 0x17)           -> uplink → cleanup → user_refresh_rtc_alarm
                                        → scheduler_set_next_alarm → set_daily_alarm

Observe (log stlink):
  - "mktime"        muncul  => BUG F07 BERDAMPAK (time_t 32-bit, alarm harian gagal)
  - "SC: Next"      muncul, tanpa mktime error => alarm harian sukses (time_t 64-bit / laten)

Kalau log stlink tidak tersedia, test hanya melapor status trigger (tak bisa
menyimpulkan F07 — checking F07 memang butuh log).

Referensi: firmware calestek_timer.c:171, calestek_scheduler.c:75,147-151.
"""

import time
import logging
from datetime import datetime

_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81._reliability_log import LogCapture
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81._reliability_log import LogCapture

_SUBMIT_ID_1DAY = 5


class ReliabilityF07(TM81Command):

    def _set_daily_config(self) -> bool:
        # activation=1, counter=0(4B), counter_res=1, alarm=0, submit_id=5(1day),
        # timezone=7, msg_type=1  — sama urutan dgn user_set_config.py
        data = (bytes([1]) + (0).to_bytes(4, "little") + bytes([1, 0, _SUBMIT_ID_1DAY])
                + (7).to_bytes(1, "little", signed=True) + bytes([1]))
        r = self.xfer(CmdId.USR_SET_CFG, data, retries=3)
        return r.valid or r.error == "ACK"

    def _set_time_now(self) -> bool:
        now = datetime.now()
        data = bytes([now.year - 2000, now.month, now.day, now.hour, now.minute, now.second])
        r = self.xfer(CmdId.USR_SET_TIME, data, retries=3)
        return r.valid or r.error == "ACK"

    def execute(self) -> str:
        with LogCapture("stlink") as log:
            if not self._set_daily_config():
                return "NG:set config (1day) gagal"
            if not self._set_time_now():
                return "NG:set RTC gagal"

            # Force send → memicu penjadwalan alarm harian (set_daily_alarm)
            fs = self.xfer(CmdId.FORCE_SEND_LORA, timeout=10.0, retries=1)
            # 0xE6 = recovery period; scheduler tetap jalan pada siklus uplink normal
            _log.debug("force_send: valid=%s err=%s", fs.valid, fs.error)

            if not log.available:
                return ("NG:log stlink tak tersedia — F07 butuh APP_LOG untuk disimpulkan. "
                        "Pastikan ST-Link VCP terhubung & debug aktif.")

            # Tunggu scheduler menjadwalkan alarm harian
            saw_mktime = log.wait_for("mktime", timeout=15)
            saw_next   = log.contains("SC: Next") or log.contains("Next:D")

        if saw_mktime:
            return ("OK:BUG F07 BERDAMPAK — '[E] mktime.' muncul saat menjadwalkan "
                    "alarm harian (time_t 32-bit, tahun 2126 overflow). Alarm harian gagal.")
        if saw_next:
            return ("OK:TIDAK berdampak — alarm harian terjadwal ('SC: Next') tanpa error "
                    "mktime (time_t 64-bit / F07 laten pada build ini).")
        return ("NG:tak ada jejak penjadwalan alarm di log (mktime/SC:Next). "
                "Mungkin force_send recovery/ tidak aktif — coba ulang atau cek periode.")


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    sm.connect("stlink")
    print(ReliabilityF07().execute())
    sm.disconnect_all()
