"""
commands/tm81/reliability_f01.py — Test F01: out-of-bounds serial read

DESTRUCTIVE (bisa HardFault → IWDG reset ~33 dtk).

`build_send_frame` normal SELALU menulis panjang frame yang benar, jadi F01 tidak
bisa dipicu lewat xfer biasa. Di sini frame disusun MENTAH dengan declared length
palsu 65535 sementara frame fisik cuma ~14 byte:

  ff ff | 01 0f 00 | FF | 02 | 00(cmd ping) | FF FF(ext_len=65535) | 03 | CRC | 04

Parser firmware membaca effective_frame_len=65535 lalu mengindeks 65534 pada buffer
1024 (calestek_scp.c:329) — sebelum memvalidasi batas atas → baca di luar buffer.

Checking (best-effort, sama gaya F02):
  1. Reset config → baseline alarm
  2. Kirim frame mentah palsu
  3a. Device tidak balas → tunggu 40s (IWDG) → ping → cek bit WDT (0x10)
  3b. Device balas error frame → ditolak aman (kemungkinan dipatch)

CATATAN JUJUR: apakah OOB read men-trigger HardFault tergantung alamat/memori.
Bit WDT muncul = PASTI crash (bug). Tapi "tidak crash" TIDAK sepenuhnya
membuktikan aman — bisa jadi OOB read diam-diam tanpa fault. Bukti paling tegas
tetap lewat debugger (breakpoint di cek EOT, inspeksi index 65534).

Referensi: firmware calestek_scp.c:277-336. SWM reliability review F01.
"""

import time
import threading
import logging

_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81._reliability_log import LogCapture
    import serial_manager as sm
    from serial_comm import ParseResult
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81._reliability_log import LogCapture
    import serial_manager as sm
    from serial_comm import ParseResult

_ALARM_STATUS_OFFSET = 10
_WDT_BIT             = 1 << 4     # 0x10
_WAIT_WDT_S          = 40
_PING_TRIES          = 8
_PING_GAP_S          = 3
_HEADER_PREFIX       = b"\x01\x0f"


class ReliabilityF01(TM81Command):

    RETRIES = 1

    def _build_bad_frame(self, comm) -> bytes:
        """Frame mentah: ping (cmd 0), FRAME_LENGTH=0xFF, ext_len palsu = 65535."""
        parser = comm._parser
        cmd_bytes = (
            b"\x01\x0f\x00"     # prefix
            + b"\xff"           # FRAME_LENGTH = extended marker
            + b"\x02"           # STX
            + b"\x00"           # CMD = ping
            + (65535).to_bytes(2, "little")   # ext_len PALSU (fisik cuma ~14B)
            + b"\x03"           # ETX
        )
        crc_val = parser._calc_crc(cmd_bytes)
        crc_b   = crc_val.to_bytes(parser._crc_bytes,
                                   "big" if parser._crc_bigend else "little")
        return b"\xff\xff" + cmd_bytes + crc_b + b"\x04"

    def _send_raw(self, frame: bytes, timeout: float = 3.0) -> ParseResult:
        """Kirim frame mentah + tunggu satu frame balasan (mirip base.xfer)."""
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            return ParseResult(raw=b"", payload=b"", valid=False, error="Koneksi tidak terhubung")

        lock = sm.get_lock(self._conn)
        with lock:
            comm._parser._buf.clear()
            try:
                comm._port.reset_input_buffer()
            except Exception:
                pass

            result = [None]
            event = threading.Event()

            def _on_data(r, _res=result, _ev=event):
                _res[0] = r
                _ev.set()

            comm.on_data(_on_data)
            try:
                comm._port.write(frame)
            except Exception as e:
                comm.off_data(_on_data)
                return ParseResult(raw=b"", payload=b"", valid=False, error=str(e))
            event.wait(timeout=timeout)
            comm.off_data(_on_data)

        pr = result[0]
        if pr is None:
            return ParseResult(raw=b"", payload=b"", valid=False, error="Timeout")
        return pr

    def _read_alarm(self):
        r = self.xfer(CmdId.USR_GET_CONFIG, retries=3)
        if not r.valid or len(r.payload) < 14:
            return None
        return r.payload[_ALARM_STATUS_OFFSET]

    def execute(self) -> str:
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            return "NG:koneksi ch340 tidak terhubung"

        # 1. baseline
        r = self.xfer(CmdId.USR_RESET_CONFIG, retries=3)
        if not r.valid and r.error != "ACK":
            return f"NG:reset config gagal ({r.error})"
        before = self._read_alarm()
        if before is None:
            return "NG:tidak bisa baca config awal"

        with LogCapture("stlink") as logcap:
            # 2. kirim frame mentah palsu
            frame = self._build_bad_frame(comm)
            _log.debug("TX F01 raw (%dB): %s", len(frame), frame.hex(" "))
            r = self._send_raw(frame, timeout=3.0)

            # 3b. device balas → ditolak aman
            if r.valid or r.error in ("ACK", "NAK"):
                return (f"OK:TIDAK crash — device membalas '{r.error}' "
                        f"(frame ditolak aman / kemungkinan dipatch).")

            # 3a. tidak ada balasan → mungkin HardFault, tunggu IWDG
            _log.debug("tak ada balasan (%s) — tunggu %ds", r.error, _WAIT_WDT_S)
            time.sleep(_WAIT_WDT_S)

            back = False
            for _ in range(_PING_TRIES):
                p = self.xfer(CmdId.PING, retries=1)
                if p.valid or p.error == "ACK":
                    back = True
                    break
                time.sleep(_PING_GAP_S)

            log_iwdg = logcap.contains("F:IWDG")

        if not back:
            return (f"NG:device tidak kembali setelah "
                    f"{_WAIT_WDT_S + _PING_TRIES * _PING_GAP_S}s — kemungkinan brick.")

        after = self._read_alarm()
        if after is None:
            return "NG:device kembali tapi config tak terbaca"

        log_note = " [log: F:IWDG]" if log_iwdg else ""
        if ((after & _WDT_BIT) and not (before & _WDT_BIT)) or log_iwdg:
            return ("OK:BUG F01 TERBUKTI — frame declared-length palsu memicu crash, "
                    "IWDG reset (bit WDT 0x%02x→0x%02x).%s" % (before, after, log_note))
        return ("OK:device reboot tapi tanpa bit WDT baru (0x%02x→0x%02x) — "
                "tak crash / sebab lain. Bukti tegas F01 perlu debugger." % (before, after))


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as _smm
    _smm.connect("ch340")
    print(ReliabilityF01().execute())
    _smm.disconnect_all()
