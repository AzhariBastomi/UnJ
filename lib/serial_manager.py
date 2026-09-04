"""
serial_manager.py - Multi-connection serial manager.

Mendukung beberapa port bersamaan (misalnya STLink + UART device).
Konfigurasi dibaca dari config.json di root project.

Cara pakai:
    import serial_manager as sm

    # Koneksi default (diatur di config.json -> serial.default)
    sm.connect()
    resp = sm.send_and_wait("TEST_LED")

    # Koneksi bernama
    sm.connect("stlink")
    sm.connect("uart")
    resp = sm.send_and_wait("TEST_COMM", conn="uart")

    sm.disconnect("uart")
    sm.disconnect_all()
"""

from __future__ import annotations
import logging
import os, sys, json, threading
from typing import Optional
from serial_comm import SerialComm, SerialConfig, FrameParser, RawLineParser, TM81Parser

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Baca config.json
# ---------------------------------------------------------------------------

def _load_json() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    try:
        with open(os.path.abspath(path)) as f:
            return json.load(f).get("serial", {})
    except Exception:
        return {}

_CFG = _load_json()

# Nama koneksi default ("uart" jika tidak diset)
DEFAULT_CONN = _CFG.get("default", "uart")

# Dict semua konfigurasi koneksi dari config.json
_CONN_DEFS: dict[str, dict] = _CFG.get("connections", {})
# Override bluetooth connection from config/bexa.json (user-editable)
_BEXA_CFG = os.path.join(os.path.dirname(__file__), "..", "config", "bexa.json")
try:
    import json as _json_bexa
    with open(_BEXA_CFG, encoding="utf-8") as _f:
        _bexa = _json_bexa.load(_f)
    _bt = _CONN_DEFS.setdefault("bluetooth", {})
    for _k in ("port_windows", "port_linux", "baudrate", "device_name"):
        if _k in _bexa:
            _bt[_k] = _bexa[_k]
except Exception:
    pass

# Fallback jika config.json tidak punya "connections" (format lama)
if not _CONN_DEFS:
    _CONN_DEFS = {
        DEFAULT_CONN: {
            "device_name": _CFG.get("device_name", "USB Serial"),
            "baudrate":    _CFG.get("baudrate",    115200),
            "timeout":     _CFG.get("timeout",     2.0),
        }
    }


def _make_parser(name: str):
    """Pilih parser berdasarkan field 'parser' di config.json.

    Config options per koneksi:
        parser      : "frame" | "crc" | "raw"   (default: "frame")
        frame_start : karakter awal frame         (default: "<")
        frame_end   : karakter akhir frame        (default: ">")
    """
    d     = _CONN_DEFS.get(name, {})
    kind  = d.get("parser", "frame")
    start = d.get("frame_start", "<").encode()
    end   = d.get("frame_end",   ">").encode()
    if kind == "raw":
        return RawLineParser()
    elif kind == "tm81":
        return TM81Parser(
            crc_type  = d.get("crc_type",  "crc32mpeg2"),
            crc_bytes = d.get("crc_bytes", 4),
            crc_bigend= d.get("crc_bigend", False),
        )
    else:
        return FrameParser(start=start, end=end)


def _direct_port(name: str) -> Optional[str]:
    """
    Kembalikan port langsung jika koneksi menggunakan port_windows / port_linux.
    Return None jika koneksi pakai device_name scan biasa.
    """
    d = _CONN_DEFS.get(name, {})
    if "port_windows" in d or "port_linux" in d:
        if sys.platform.startswith("win"):
            return d.get("port_windows")
        else:
            return d.get("port_linux")
    return None


def _scan_port_by_name(keyword: str) -> Optional[str]:
    """Cari COM port yang cocok dengan keyword (description/manufacturer/product/hwid)."""
    if not keyword:
        return None
    kw = keyword.lower()
    try:
        import serial.tools.list_ports as lp
        for p in lp.comports():
            haystack = " ".join(str(x or "") for x in (
                p.description, p.manufacturer, p.product, p.hwid, p.name, p.device))
            if kw in haystack.lower():
                return p.device
    except Exception as e:
        _log.debug("[serial_manager] scan port gagal: %s", e)
    return None


def _available_ports() -> list:
    try:
        import serial.tools.list_ports as lp
        return [p.device for p in lp.comports()]
    except Exception:
        return []


def _resolve_port(name: str) -> Optional[str]:
    """
    Tentukan port yang dipakai untuk koneksi `name`.

    Urutan:
      1. Jika ada `device_name` -> scan port berdasarkan nama device (auto-follow
         kalau Windows memindahkan COM port-nya).
      2. Kalau scan gagal / tidak ada device_name -> pakai port_windows/port_linux
         dari config sebagai fallback.
      3. Return None -> SerialComm akan auto-find via device_name seperti biasa.
    """
    d = _CONN_DEFS.get(name, {})
    fixed = _direct_port(name)
    kw    = d.get("device_name", "")

    if kw:
        found = _scan_port_by_name(kw)
        if found:
            if fixed and found != fixed:
                _log.info("[serial_manager] %s: %r ditemukan di %s (config: %s)",
                          name, kw, found, fixed)
            return found
        if fixed:
            _log.warning("[serial_manager] %s: device %r tidak terdeteksi, "
                         "fallback ke %s", name, kw, fixed)

    if fixed:
        ports = _available_ports()
        if ports and fixed not in ports:
            _log.warning("[serial_manager] %s: port %s tidak ada di sistem. "
                         "Port tersedia: %s", name, fixed, ", ".join(ports))
        return fixed

    return None


def _make_config(name: str) -> SerialConfig:
    """Buat SerialConfig dari entry di config.json."""
    d = _CONN_DEFS.get(name, {})
    if not d:
        raise KeyError(f"Koneksi '{name}' tidak ditemukan di config.json")
    # Jika ada port langsung (bluetooth), device_name tidak dipakai untuk scan
    device_name = d.get("device_name", _direct_port(name) or "USB Serial")
    return SerialConfig(
        device_name    = device_name,
        baudrate       = d.get("baudrate",    115200),
        timeout        = d.get("timeout",     2.0),
        bytesize       = d.get("bytesize",    8),
        parity         = d.get("parity",      "N"),
        stopbits       = d.get("stopbits",    1),
        xonxoff        = d.get("xonxoff",     False),
        rtscts         = d.get("rtscts",      False),
        dsrdtr         = d.get("dsrdtr",      False),
        cmd_terminator = b'\n',
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Singleton registry  {name: SerialComm}
# ---------------------------------------------------------------------------

_conns: dict[str, SerialComm] = {}

# Per-connection lock — satu lock per koneksi.
# Setiap xfer() (keepalive MAUPUN test command) acquire lock ini sebelum
# kirim data dan release setelah dapat response / timeout.
# Siapapun yang coba xfer() saat koneksi sedang dipakai tinggal tunggu —
# tidak ada tabrakan di serial port tanpa perlu mekanisme pause/resume manual.
_conn_locks: dict[str, threading.Lock] = {}


def get_lock(conn: str = None) -> threading.Lock:
    """Return (buat jika belum ada) lock untuk koneksi `conn`."""
    name = conn or DEFAULT_CONN
    if name not in _conn_locks:
        _conn_locks[name] = threading.Lock()
    return _conn_locks[name]


def get_comm(conn: str = None) -> Optional[SerialComm]:
    """Kembalikan SerialComm aktif untuk koneksi `conn`, atau None."""
    return _conns.get(conn or DEFAULT_CONN)


def is_connected(conn: str = None) -> bool:
    c = _conns.get(conn or DEFAULT_CONN)
    return c is not None and c.is_connected()


def list_connections() -> dict[str, bool]:
    """Return dict {name: is_connected} untuk semua koneksi yang didefinisikan."""
    result = {}
    for name in _CONN_DEFS:
        c = _conns.get(name)
        result[name] = (c is not None and c.is_connected())
    return result


# ---------------------------------------------------------------------------
# Connect / disconnect
# ---------------------------------------------------------------------------

def connect(conn: str = None, parser=None) -> bool:
    """Buka koneksi bernama conn. Jika sudah terhubung, return True."""
    name = conn or DEFAULT_CONN
    if is_connected(name):
        return True
    try:
        cfg = _make_config(name)
    except KeyError as e:
        _log.error("[serial_manager] %s", e)
        return False

    prs  = parser or _make_parser(name)
    comm = SerialComm(cfg, prs, conn_name=name)
    # Port langsung (bluetooth): scan by device_name dulu, fallback ke config
    direct = _resolve_port(name)
    ok   = comm.connect(port=direct)  # port=None -> auto-find via device_name
    if ok:
        _conns[name] = comm
        # Jika debug_rx=true di config.json, cetak semua data masuk ke terminal
        if _CONN_DEFS.get(name, {}).get("debug_rx", False):
            _register_debug_rx(comm, name)
        # Auto-reconnect: saat port terputus, coba sambung kembali otomatis
        comm.on_disconnect(lambda n=name: _on_disconnected(n))
    return ok


# Set koneksi yang sedang dalam proses reconnect — cegah double-retry
_reconnecting: set = set()


def _on_disconnected(name: str):
    """Dipanggil oleh SerialComm saat port terputus. Mulai retry loop."""
    _conns.pop(name, None)
    _log.warning("[serial] %r terputus — akan coba reconnect otomatis", name)
    _schedule_reconnect(name, delay=3.0)


def _schedule_reconnect(name: str, delay: float = 3.0):
    """Coba reconnect setelah `delay` detik, dengan exponential backoff (max 30 detik)."""
    if name in _reconnecting:
        return
    _reconnecting.add(name)

    def _retry():
        import time
        time.sleep(delay)
        _reconnecting.discard(name)
        if is_connected(name):
            return   # sudah terhubung (mungkin manual connect)
        _log.info("[serial] reconnect %r ...", name)
        ok = connect(name)
        if ok:
            _log.info("[serial] %r terhubung kembali", name)
        else:
            next_delay = min(delay * 1.5, 30.0)
            _log.debug("[serial] %r gagal, coba lagi %.0fs", name, next_delay)
            _schedule_reconnect(name, delay=next_delay)

    threading.Thread(target=_retry, daemon=True,
                     name=f"reconnect-{name}").start()


def _register_debug_rx(comm: SerialComm, name: str):
    """Daftarkan callback RX — log ke serial_comm.<name> agar muncul di debug window."""
    # Pakai logger yang sama dengan SerialComm instance (serial_comm.<name>)
    rx_log = logging.getLogger(f"serial_comm.{name}")

    def _on_data(frame):
        if frame.valid:
            payload = frame.payload.decode("utf-8", errors="replace").strip()
            rx_log.debug("RX: %r", payload)
        else:
            raw = frame.raw.decode("utf-8", errors="replace").strip()
            if raw:
                rx_log.debug("RX (raw): %r", raw)
    comm.on_data(_on_data)


def disconnect(conn: str = None):
    """Tutup koneksi bernama conn."""
    name = conn or DEFAULT_CONN
    c    = _conns.pop(name, None)
    if c:
        c.disconnect()


def disconnect_all():
    """Tutup semua koneksi aktif."""
    for name in list(_conns):
        disconnect(name)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send(command: str, conn: str = None) -> bool:
    """Kirim command ke koneksi conn. Return False jika tidak connected."""
    c = _conns.get(conn or DEFAULT_CONN)
    if not c or not c.is_connected():
        return False
    return c.send(command)


def send_and_wait(command: str, conn: str = None, timeout: float = 5.0) -> str:
    """Kirim command, tunggu satu frame response, return payload string."""
    import threading
    c = _conns.get(conn or DEFAULT_CONN)
    if not c or not c.is_connected():
        return ""

    result = [None]
    done   = threading.Event()

    def on_frame(frame):
        if frame.valid:
            result[0] = frame.payload.decode("utf-8", errors="replace").strip()
        else:
            result[0] = ""
        done.set()

    c.on_data(on_frame)
    c.send(command)
    done.wait(timeout=timeout)

    c.off_data(on_frame)

    return result[0] or ""


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------

try:
    DEFAULT_CONFIG = _make_config(DEFAULT_CONN)
except KeyError as e:
    _log.error("[serial_manager] %s", e)
    DEFAULT_CONFIG = None
