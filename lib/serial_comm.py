"""
serial_comm.py - Serial Communication Library untuk JIG Test

Arsitektur
----------
  SerialConfig   - konfigurasi koneksi (hardcode per JIG)
  ParseResult    - hasil parsing satu frame data
  BaseParser     - interface parser
  FrameParser    - parsing berdasarkan start/end marker
  SerialComm     - class utama: find port, connect, reader thread, send command

Cara pakai
----------
  from serial_comm import SerialComm, SerialConfig, FrameParser

  config = SerialConfig(device_name="Arduino")
  parser = FrameParser(start=b'<', end=b'>')
  comm   = SerialComm(config, parser)

  comm.on_data(lambda result: print(result.payload))
  comm.connect()
  comm.send("TEST_LED")
"""

from __future__ import annotations

import serial
import serial.tools.list_ports
import threading
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

# crccheck — library untuk berbagai algoritma CRC
from crccheck.crc import (
    Crc32Mpeg2,
    CrcKermit,
    Crc16,
    Crc16CcittFalse,
    Crc32,
    Crc8,
)

# Map nama string (dari config.json) ke class crccheck
_CRC_MAP = {
    "crc32mpeg2":     Crc32Mpeg2,       # TM81 IrDA
    "kermit":         CrcKermit,        # CRC-16/Kermit
    "crc16":          Crc16,            # CRC-16/IBM
    "crc16ccitt":     Crc16CcittFalse,  # CRC-16/CCITT-FALSE
    "crc32":          Crc32,            # CRC-32 standard
    "crc8":           Crc8,             # CRC-8
}


log = logging.getLogger(__name__)


# =============================================================================
# SerialConfig — semua setting koneksi di satu tempat
# =============================================================================

@dataclass
class SerialConfig:
    # --- Port discovery ---
    device_name: str  = "Arduino"        # substring yang dicari di port description

    # --- Serial parameters ---
    baudrate:    int  = 115200
    bytesize:    int  = serial.EIGHTBITS  # 5 | 6 | 7 | 8
    parity:      str  = serial.PARITY_NONE   # N | E | O | M | S
    stopbits:    float= serial.STOPBITS_ONE  # 1 | 1.5 | 2
    timeout:     float= 1.0              # read timeout (detik)

    # --- Flow control ---
    xonxoff:     bool = False            # software flow control (XON/XOFF)
    rtscts:      bool = False            # hardware flow control RTS/CTS
    dsrdtr:      bool = False            # hardware flow control DSR/DTR

    # --- Command format ---
    cmd_terminator: bytes = b'\n'        # ditambahkan di akhir setiap command


# =============================================================================
# ParseResult — hasil parsing satu frame
# =============================================================================

@dataclass
class ParseResult:
    raw:     bytes          # data mentah dari port
    payload: bytes          # isi data setelah header/footer/CRC dilepas
    valid:   bool           # True jika frame komplit dan CRC/marker cocok
    error:   str  = ""      # keterangan jika valid=False


# =============================================================================
# BaseParser — interface untuk semua parser
# =============================================================================

class BaseParser(ABC):
    """
    Override parse() untuk setiap strategi parsing.
    Reader thread memanggil feed(byte) satu byte per satu.
    Ketika satu frame komplit, on_frame(ParseResult) dipanggil.
    """

    def __init__(self):
        self._buf: bytearray = bytearray()
        self._on_frame: Optional[Callable[[ParseResult], None]] = None

    def set_frame_callback(self, fn: Callable[[ParseResult], None]):
        self._on_frame = fn

    def feed(self, byte: bytes):
        """Masukkan satu byte. Parser memutuskan kapan frame komplit."""
        self._buf += byte
        result = self.parse(self._buf)
        if result is not None:
            self._buf.clear()
            if self._on_frame:
                self._on_frame(result)

    @abstractmethod
    def parse(self, buf: bytearray) -> Optional[ParseResult]:
        """
        Return ParseResult jika buf berisi frame komplit, None jika belum.
        Jika return bukan None, buffer otomatis dikosongkan.
        """


# =============================================================================
# FrameParser — parsing berdasarkan start/end marker
# =============================================================================

class FrameParser(BaseParser):
    """
    Format: <START> payload <END>
    Contoh: b'<' ... b'>'  atau  b'STX' ... b'ETX'

    Jika include_markers=False (default), payload tidak menyertakan marker.
    """

    def __init__(self, start: bytes = b'<', end: bytes = b'>',
                 include_markers: bool = False):
        super().__init__()
        self.start           = start
        self.end             = end
        self.include_markers = include_markers

    def parse(self, buf: bytearray) -> Optional[ParseResult]:
        raw = bytes(buf)

        # Buang byte sebelum start marker
        si = raw.find(self.start)
        if si == -1:
            self._buf.clear()
            return None
        if si > 0:
            self._buf = bytearray(raw[si:])
            raw = bytes(self._buf)

        # Cari end marker setelah start
        ei = raw.find(self.end, len(self.start))
        if ei == -1:
            return None   # frame belum komplit

        frame   = raw[si : ei + len(self.end)]
        payload = raw[si + len(self.start) : ei]

        return ParseResult(
            raw     = frame,
            payload = payload if not self.include_markers else frame,
            valid   = True,
        )


# =============================================================================
# TM81Parser — protocol TM81 IrDA via CH340
# =============================================================================

class TM81Parser(BaseParser):
    """
    Protocol TM81 (IrDA via CH340), CRC via crccheck library.

    SEND frame:
        0xFF 0xFF | 0x01 0x0F 0x00 | LEN | 0x02 | CMD_ID | DATA | 0x03 | CRC(crc_bytes LE) | 0x04

    RECEIVE:
        ACK  : 0x11
        NAK  : 0x0F
        Frame: 0x01 0x0F CMD LEN 0x02 ... 0x03 CRC EOT

    Konfigurasi (dari config.json):
        crc_type   : nama algoritma CRC (lihat _CRC_MAP), default "crc32mpeg2"
        crc_bytes  : ukuran CRC dalam byte, default 4
        crc_bigend : urutan byte CRC, default False (little-endian)
    """

    ACK           = b"\x11"
    NAK           = b"\x0f"
    EOT           = b"\x04"
    HEADER_PREFIX = b"\x01\x0f"

    # Nama command TM81 untuk log TX yang lebih informatif
    _CMD_NAMES: "dict[int, str]" = {
        0x00: "PING",              0x01: "IRDA_DISABLE",
        0x02: "SENSOR_GET_CFG",   0x03: "SENSOR_RESET_CFG",
        0x04: "SENSOR_GET_DATA",  0x05: "USR_REBOOT_BL",
        0x06: "USR_SYNC_CFG",     0x07: "USR_SET_CFG",
        0x08: "USR_GET_CFG",      0x09: "USR_RESET_CFG",
        0x0A: "USR_GET_TIME",     0x0B: "USR_SET_TIME",
        0x0C: "USR_GET_VER",      0x0D: "USR_TEST_WDT",
        0x0E: "ENTER_STANDBY",    0x0F: "SET_DEV_EUI",
        0x10: "SET_JOIN_EUI",     0x11: "SET_APP_KEY",
        0x12: "SET_NW_KEY",       0x13: "SET_DEV_ADDR",
        0x14: "SET_JOIN_MODE",    0x15: "SET_DEV_CLASS",
        0x16: "GET_LORA_DATA",    0x17: "FORCE_SEND_LORA",
        0x18: "USAGE_READ",       0x19: "USAGE_WRITE",
        0x1A: "GET_DEV_INFO",     0x1B: "DEV_GET_ID",
        0x1C: "DEV_SET_ID",       0x1D: "SET_LORA_DATA",
        0x1E: "GET_CHIP_ID",      0x1F: "CC_GET_TEMP",
        0x20: "CC_RESET_ACR",     0x21: "CC_GET_ACR",
        0x22: "SOFT_RESET",       0x23: "GET_LAST_SUBMIT",
        100:  "BL_SET_RDY",       101:  "BL_FW_DATA",
        102:  "BL_GOTO_APP",      106:  "BL_GET_OTA_PROGRESS",
        107:  "BL_OTA_CLEAR",     108:  "BL_GET_UPTIME",
    }

    def __init__(self, crc_type: str = "crc32mpeg2",
                 crc_bytes: int = 4, crc_bigend: bool = False):
        super().__init__()
        self._crc_cls    = _CRC_MAP.get(crc_type, Crc32Mpeg2)
        self._crc_bytes  = crc_bytes
        self._crc_bigend = crc_bigend
        self._log        = log  # default ke module logger; di-override oleh SerialComm

    def set_logger(self, logger) -> None:
        """Inject per-connection logger dari SerialComm agar TX/RX log masuk ke window yang benar."""
        self._log = logger

    def _calc_crc(self, data: bytes) -> int:
        return self._crc_cls.calc(data)

    def build_send_frame(self, cmd_id: int, data: bytes = b"") -> bytes:
        """Bangun frame TX lengkap untuk CMD_ID tertentu.

        Frame kecil  (total ≤ 255B): ff ff | 01 0f 00 | LEN(1B) | 02 | CMD | DATA | 03 | CRC | 04
        Frame besar  (total > 255B): ff ff | 01 0f 00 | FF | 02 | CMD | EXT_LEN(2B LE) | DATA | 03 | CRC | 04
          EXT_LEN disisipkan SETELAH CMD (bukan antara FF dan STX).
          EXT_LEN = byte dari '01 0f 00' sampai '04' inklusif = 10 + data_len + crc_bytes.
          CRC dihitung atas cmd_bytes yang sudah termasuk ext_len.
        """
        data_len  = len(data)
        total_len = 12 + data_len
        if total_len <= 0xFF:
            # Frame normal: cmd_len 1 byte
            cmd_bytes = (
                b"\x01\x0f\x00"
                + total_len.to_bytes(1, "little")
                + b"\x02"
                + cmd_id.to_bytes(1, "little")
                + data
                + b"\x03"
            )
        else:
            # Frame besar: cmd_len=0xFF, ext_len(2B LE) disisipkan setelah CMD
            # ext_len = 10 + data_len + crc_bytes (byte dari prefix sampai EOT inklusif)
            ext_len = (10 + data_len + self._crc_bytes).to_bytes(2, "little")
            cmd_bytes = (
                b"\x01\x0f\x00"
                + b"\xff"
                + b"\x02"
                + cmd_id.to_bytes(1, "little")
                + ext_len
                + data
                + b"\x03"
            )
        crc_val   = self._calc_crc(cmd_bytes)
        crc_b     = crc_val.to_bytes(self._crc_bytes,
                                     "big" if self._crc_bigend else "little")
        frame    = b"\xff\xff" + cmd_bytes + crc_b + b"\x04"
        cmd_name = self._CMD_NAMES.get(cmd_id, "?")
        # Truncate hex dump untuk frame besar agar debug console tidak berat
        _MAX_HEX = 32
        if len(frame) > _MAX_HEX:
            hex_str = " ".join(f"{b:02x}" for b in frame[:_MAX_HEX]) + " ..."
        else:
            hex_str = " ".join(f"{b:02x}" for b in frame)
        self._log.debug("[TM81 TX] cmd=0x%02x (%s) crc=%#010x len=%dB  %s",
                        cmd_id, cmd_name, crc_val, len(frame), hex_str)
        return frame

    def parse(self, buf: bytearray) -> Optional[ParseResult]:
        raw = bytes(buf)

        # --- ACK ---
        if raw == self.ACK:
            self._log.debug("[TM81 RX] ACK (0x11)")
            self._buf.clear()
            return ParseResult(raw=raw, payload=b"", valid=True, error="ACK")

        # --- NAK ---
        if raw == self.NAK:
            self._log.debug("[TM81 RX] NAK (0x0f)")
            self._buf.clear()
            return ParseResult(raw=raw, payload=b"", valid=False, error="NAK")

        # --- Cari header 0x01 0x0F ---
        si = raw.find(self.HEADER_PREFIX)
        if si == -1:
            if self.ACK[0] in raw:
                self._buf = bytearray(raw[raw.index(self.ACK[0]):])
                return None
            # Simpan byte terakhir jika bisa jadi awal HEADER_PREFIX
            if raw and raw[-1] == self.HEADER_PREFIX[0]:
                self._buf = bytearray(raw[-1:])
            else:
                self._buf.clear()
            return None
        if si > 0:
            self._buf = bytearray(raw[si:])
            raw = bytes(self._buf)

        # Butuh minimal 4 byte untuk baca header + LEN: 01 0F CMD LEN
        if len(raw) < 4:
            return None

        # --- Tentukan panjang total frame dari field LEN (BUKAN dengan mencari
        # byte 0x04 pertama!). Byte 0x04 bisa muncul sebagai data biasa di
        # tengah payload (mis. GET_DEV_INFO), yang dulu bikin frame kepotong
        # duluan sebelum EOT asli — hasil parse jadi salah/pendek secara
        # intermiten tergantung isi data yang kebetulan sama dengan 0x04. ---
        header_extra = 0
        total_len    = raw[3]
        if total_len == 0xFF:
            # Frame besar: LEN sentinel 0xFF, panjang asli ada di 2 byte berikutnya (LE)
            if len(raw) < 6:
                return None
            total_len    = int.from_bytes(raw[4:6], "little")
            header_extra = 2

        crc_size = self._crc_bytes
        min_len  = 4 + header_extra + 1 + 1 + crc_size + 1  # header+STX+ETX+CRC+EOT, payload kosong
        if total_len < min_len:
            # LEN tidak masuk akal (frame korup/ke-mis-sync) — buang 1 byte,
            # coba cari header lagi dari posisi berikutnya supaya tidak stuck.
            self._buf = bytearray(raw[1:])
            return None

        if len(raw) < total_len:
            return None   # belum lengkap, tunggu byte berikutnya

        frame = raw[:total_len]
        if frame[-1:] != self.EOT:
            # EOT tidak ada di posisi yang diharapkan -> LEN salah/frame korup.
            self._buf = bytearray(raw[1:])
            return None

        # CRC tidak diverifikasi di RX (referensi tm81-command-tester juga tidak cek CRC RX)
        payload  = frame[4 + header_extra + 1: -(crc_size + 2)]
        hex_str  = " ".join(f"{b:02x}" for b in frame)
        self._log.debug("[TM81 RX] len=%dB  %s", len(frame), hex_str)
        if payload:
            self._log.debug("[TM81 RX] payload=%s", payload.hex(" "))
        self._buf = bytearray(raw[total_len:])
        return ParseResult(raw=frame, payload=payload, valid=True)


# =============================================================================
# RawLineParser — fallback sederhana: satu baris = satu frame
# =============================================================================

class RawLineParser(BaseParser):
    """Frame = satu baris yang diakhiri terminator (default \\n)."""

    def __init__(self, terminator: bytes = b'\n'):
        super().__init__()
        self.terminator = terminator

    def parse(self, buf: bytearray) -> Optional[ParseResult]:
        raw = bytes(buf)
        idx = raw.find(self.terminator)
        if idx == -1:
            return None
        line = raw[: idx]
        return ParseResult(raw=line + self.terminator,
                           payload=line.strip(), valid=True)


# =============================================================================
# SerialComm — class utama
# =============================================================================

class SerialComm:
    """
    Mengelola koneksi serial: find port, connect, reader thread, send.

    Callbacks
    ---------
    on_data(fn)       : dipanggil setiap ParseResult komplit diterima
    on_raw(fn)        : dipanggil setiap kali bytes mentah diterima dari port (sebelum parsing)
    on_connect(fn)    : dipanggil saat berhasil connect
    on_disconnect(fn) : dipanggil saat disconnect / port hilang
    """

    def __init__(self, config: SerialConfig, parser: BaseParser,
                 conn_name: str = ""):
        self._config   = config
        self._parser   = parser
        self._port: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

        self._cb_data:       list[Callable] = []
        self._cb_raw:        list[Callable] = []
        self._cb_connect:    list[Callable] = []
        self._cb_disconnect: list[Callable] = []
        self._lock           = threading.Lock()
        self._disconnected   = False

        # Logger per-koneksi: serial_comm.<conn_name> atau serial_comm
        self._log = (logging.getLogger(f"serial_comm.{conn_name}")
                     if conn_name else log)

        self._parser.set_frame_callback(self._on_frame)
        # Inject per-connection logger ke parser agar TX/RX log pakai nama yang sama
        if hasattr(self._parser, "set_logger"):
            self._parser.set_logger(self._log)

    # ------------------------------------------------------------------
    # Port discovery
    # ------------------------------------------------------------------

    def find_port(self) -> Optional[str]:
        """Cari port berdasarkan device_name di deskripsi."""
        keyword = self._config.device_name.lower()
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if keyword in desc:
                return p.device
        return None

    # ------------------------------------------------------------------
    # Connect / disconnect
    # ------------------------------------------------------------------

    def connect(self, port=None):
        """Buka koneksi serial. Jika port=None, cari otomatis via find_port()."""
        if port is None:
            port = self.find_port()
        if port is None:
            self._log.warning("Port tidak ditemukan untuk device: %s", self._config.device_name)
            return False
        try:
            self._port = serial.Serial(
                port     = port,
                baudrate = self._config.baudrate,
                bytesize = self._config.bytesize,
                parity   = self._config.parity,
                stopbits = self._config.stopbits,
                timeout  = self._config.timeout,
                xonxoff  = self._config.xonxoff,
                rtscts   = self._config.rtscts,
                dsrdtr   = self._config.dsrdtr,
            )
        except serial.SerialException as e:
            self._log.error("Gagal buka port %s: %s", port, e)
            msg = str(e).lower()
            if "access is denied" in msg or "permission" in msg:
                self._log.error(
                    "Hint: %s sedang dipakai proses lain (instance app sebelumnya, "
                    "Tera Term/PuTTY/Serial Monitor), atau device Bluetooth-nya "
                    "belum aktif / port-nya bukan COM 'Outgoing'.", port)
            return False

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

        for fn in self._cb_connect:
            fn(port)
        self._log.info("Terhubung ke %s", port)
        return True

    def disconnect(self):
        """Tutup koneksi serial dan hentikan reader thread."""
        already = self._disconnected
        self._disconnected = True
        self._stop_evt.set()
        if self._port and self._port.is_open:
            self._port.close()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._port = None
        if not already:
            with self._lock:
                cbs = list(self._cb_disconnect)
            for fn in cbs:
                fn()

    def is_connected(self):
        return self._port is not None and self._port.is_open

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send(self, data):
        """
        Kirim data ke port serial.
        - bytes / bytearray  -> dikirim langsung
        - str                -> di-encode UTF-8 + cmd_terminator
        """
        if not self.is_connected():
            return False
        if isinstance(data, (bytes, bytearray)):
            raw = bytes(data)
        else:
            raw = str(data).encode() + self._config.cmd_terminator
        try:
            self._port.write(raw)
            return True
        except serial.SerialException as e:
            self._log.error("Gagal kirim: %s", e)
            return False

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_data(self, fn):
        with self._lock:
            self._cb_data.append(fn)

    def off_data(self, fn):
        with self._lock:
            try: self._cb_data.remove(fn)
            except ValueError: pass

    def on_raw(self, fn):
        """Daftarkan callback untuk bytes mentah RX (dipanggil sebelum parsing)."""
        with self._lock:
            self._cb_raw.append(fn)

    def off_raw(self, fn):
        with self._lock:
            try: self._cb_raw.remove(fn)
            except ValueError: pass

    def on_connect(self, fn):
        with self._lock:
            self._cb_connect.append(fn)

    def on_disconnect(self, fn):
        with self._lock:
            self._cb_disconnect.append(fn)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reader(self):
        """Thread: baca dalam chunk, feed ke parser byte per byte."""
        while not self._stop_evt.is_set():
            try:
                if self._port and self._port.is_open:
                    n = max(1, self._port.in_waiting)
                    data = self._port.read(n)
                    if data:
                        with self._lock:
                            raw_cbs = list(self._cb_raw)
                        for fn in raw_cbs:
                            fn(data)
                    for b in data:
                        self._parser.feed(bytes([b]))
            except serial.SerialException as e:
                self._log.warning("Reader error: %s", e)
                break
        # Pastikan port ditutup dan di-clear agar is_connected() return False
        try:
            if self._port and self._port.is_open:
                self._port.close()
        except Exception:
            pass
        self._port = None

        if not self._disconnected:
            self._disconnected = True
            with self._lock:
                cbs = list(self._cb_disconnect)
            for fn in cbs:
                fn()

    def _on_frame(self, result):
        with self._lock:
            cbs = list(self._cb_data)
        for fn in cbs:
            fn(result)
