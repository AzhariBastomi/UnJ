"""
commands/tm81/_reliability_log.py — helper tangkap log APP_LOG device via ST-Link VCP.

Device mengirim APP_LOG lewat koneksi 'stlink' (STLink Virtual COM, debug_rx=true).
Helper ini merekam RX mentah koneksi itu selama satu blok pengujian, lalu bisa
dicari polanya (mis. "[E] mktime.", "ALM: F:IWDG").

Pakai:
    with LogCapture() as log:
        ... kirim perintah via ch340 ...
        hit = log.wait_for("mktime", timeout=15)
    print(log.text())

Kalau koneksi stlink tidak ada / gagal, LogCapture tidak error — .available=False
dan semua pencarian mengembalikan False, sehingga test tetap jalan (checking log
jadi opsional, bukan syarat).
"""

import time
import logging

_log = logging.getLogger(__name__)

try:
    import serial_manager as sm
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    import serial_manager as sm


class LogCapture:
    def __init__(self, conn: str = "stlink"):
        self._conn = conn
        self._buf = bytearray()
        self._comm = None
        self.available = False

    def _on_raw(self, data: bytes):
        try:
            self._buf.extend(data)
        except Exception:
            pass

    def __enter__(self):
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            try:
                sm.connect(self._conn)
                comm = sm.get_comm(self._conn)
            except Exception as e:
                _log.debug("LogCapture: gagal connect '%s': %s", self._conn, e)
                comm = None
        if comm is not None and comm.is_connected() and hasattr(comm, "on_raw"):
            comm.on_raw(self._on_raw)
            self._comm = comm
            self.available = True
        else:
            _log.debug("LogCapture: koneksi '%s' tidak tersedia — log opsional dilewati", self._conn)
        return self

    def __exit__(self, *exc):
        if self._comm is not None and hasattr(self._comm, "off_raw"):
            try:
                self._comm.off_raw(self._on_raw)
            except Exception:
                pass
        return False

    def text(self) -> str:
        return bytes(self._buf).decode("utf-8", errors="replace")

    def contains(self, pattern: str) -> bool:
        return pattern in self.text()

    def wait_for(self, pattern: str, timeout: float = 15.0, poll: float = 0.5) -> bool:
        """Tunggu sampai `pattern` muncul di log, atau timeout. False kalau log tak tersedia."""
        if not self.available:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if pattern in self.text():
                return True
            time.sleep(poll)
        return pattern in self.text()
