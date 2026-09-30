"""
commands/tm81/reliability_f02.py — Test F02: History buffer overwrite → hang/WDT

DESTRUCTIVE. Mengirim frame usage_history_write cacat (payload 128 byte, day=0)
yang membuat firmware menghitung data_len=125 ke buffer 124 → memset(0xFFFFFFFF)
→ HardFault → HardFault_Handler while(1) → IWDG reset (~33 dtk).

Alur (persis permintaan):
  1. Reset user config   -> alarm_status baseline bersih
  2. Baca config         -> catat alarm_status sebelum
  3. Kirim frame cacat    -> device HardFault (tidak ada balasan)
  4. Tunggu ~40 dtk       -> IWDG reset + boot
  5. Ping                 -> pastikan device kembali
  6. Baca config          -> cek bit WDT (0x10) di alarm_status

Checking:
  alarm_status = payload[10] respons get-config (14 byte).
  Bit WDT = 1 << calestek_ALARM_ID_WDT = 1 << 4 = 0x10.
  Firmware saat reboot dari IWDG mengangkat alarm ini (calestek_task.c:1109).

Verdict:
  - Bit WDT muncul (0->1) setelah hang+reboot  => BUG F02 TERBUKTI.
  - Device membalas ACK/NAK tanpa hang          => tidak hang (sudah dipatch / aman).
  - Device tidak kembali setelah 40 dtk         => NG (kemungkinan brick, perlu reflash).

Siapkan reflash (recover_bricked_mcu / ST-Link) sebelum menjalankan.
Referensi: firmware calestek_scp.c:1074, SWM reliability review F02.
"""

import time
import logging

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

_ALARM_STATUS_OFFSET = 10          # payload[10] = alarm_status (USER_SCP_ID_ALARM_STATUS)
_WDT_BIT             = 1 << 4      # 1 << calestek_ALARM_ID_WDT
_WAIT_WDT_S          = 40         # IWDG ~33s + boot
_PING_TRIES          = 8          # ping ulang setelah reboot
_PING_GAP_S          = 3


class ReliabilityF02(TM81Command):

    # Frame cacat tidak boleh di-retry (device sudah crash, buang waktu).
    RETRIES = 1

    def _read_alarm(self):
        """Return (alarm_status:int) atau None kalau gagal baca config."""
        r = self.xfer(CmdId.USR_GET_CONFIG, retries=3)
        if not r.valid or len(r.payload) < 14:
            return None
        return r.payload[_ALARM_STATUS_OFFSET]

    def execute(self) -> str:
        # 1. Reset config → baseline alarm bersih
        r = self.xfer(CmdId.USR_RESET_CONFIG, retries=3)
        if not r.valid and r.error != "ACK":
            return f"NG:reset config gagal ({r.error})"

        # 2. Baca alarm sebelum
        before = self._read_alarm()
        if before is None:
            return "NG:tidak bisa baca config awal (device tidak merespons)"
        _log.debug("alarm_status sebelum = 0x%02x", before)

        # 3-6 dibungkus LogCapture agar bisa konfirmasi reset lewat APP_LOG stlink.
        with LogCapture("stlink") as logcap:
            # 3. Kirim frame cacat: day=0, month=9, year=26, + 125 byte 0xAA (total 128)
            bad = bytes([0, 9, 26]) + b"\xaa" * 125
            r = self.xfer(CmdId.USAGE_HISTORY_WRITE, bad, timeout=3.0, retries=1)

            if r.valid or r.error in ("ACK", "NAK"):
                # Device membalas → TIDAK hang (dipatch / aman).
                after = self._read_alarm()
                aft = "0x%02x" % after if after is not None else "?"
                return (f"OK:TIDAK HANG — device membalas '{r.error}' tanpa crash "
                        f"(alarm_status={aft}). Firmware tampak sudah aman/dipatch.")

            # 4. Tidak ada balasan → kemungkinan HardFault. Tunggu IWDG.
            _log.debug("frame cacat tanpa balasan (%s) — tunggu %ds untuk IWDG",
                       r.error, _WAIT_WDT_S)
            time.sleep(_WAIT_WDT_S)

            # 5. Ping sampai device kembali
            back = False
            for i in range(_PING_TRIES):
                p = self.xfer(CmdId.PING, retries=1)
                if p.valid or p.error == "ACK":
                    back = True
                    break
                time.sleep(_PING_GAP_S)

            # Bukti reset dari log: "[D] ALM: F:IWDG" saat reboot (task.c:1110)
            log_iwdg = logcap.contains("F:IWDG")
            log_rst  = logcap.contains("RST: Flag")

        if not back:
            return (f"NG:device TIDAK kembali setelah {_WAIT_WDT_S + _PING_TRIES * _PING_GAP_S}s "
                    f"— kemungkinan brick, perlu reflash.")

        # 6. Baca alarm sesudah
        after = self._read_alarm()
        if after is None:
            return "NG:device kembali tapi config tak terbaca"
        _log.debug("alarm_status sesudah = 0x%02x", after)

        wdt_before = bool(before & _WDT_BIT)
        wdt_after  = bool(after & _WDT_BIT)
        log_note = " [log: F:IWDG]" if log_iwdg else (" [log: RST]" if log_rst else "")

        if wdt_after and not wdt_before:
            return (f"OK:BUG F02 TERBUKTI — device HANG lalu IWDG reset. "
                    f"Bit WDT muncul: alarm_status 0x%02x → 0x%02x.%s" % (before, after, log_note))
        if log_iwdg:
            return (f"OK:BUG F02 TERBUKTI (via log) — device reboot dgn 'F:IWDG'. "
                    f"alarm_status 0x%02x → 0x%02x.%s" % (before, after, log_note))
        if wdt_after and wdt_before:
            return (f"OK:device reboot & WDT set, tapi bit WDT sudah ada sebelum tes "
                    f"(0x%02x→0x%02x) — reset config tidak membersihkannya, tak bisa pastikan." % (before, after))
        return (f"OK:device reboot tapi TANPA bit WDT (0x%02x→0x%02x) — "
                f"reboot dari sebab lain / tidak sesuai F02." % (before, after))


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    print(ReliabilityF02().execute())
    sm.disconnect_all()
