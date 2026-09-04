"""
commands/bexa/base.py — Base class untuk semua command Bexa FTM.

Frame Format (FTM):
    [0x0E][LEN_LSB][LEN_MSB][TID=0x00][CMD][CRC_LSB][CRC_MSB]

Frame Format (Command):
    [CMD_ID][LEN_LSB][LEN_MSB][TID][PAYLOAD...][CRC_LSB][CRC_MSB]

ACK Response:
    [0xFF][LEN_LSB][LEN_MSB][TID][MSG_ID][STATUS][PAYLOAD_PRESENT][PL_LEN_LSB][PL_LEN_MSB][PAYLOAD...][CRC_LSB][CRC_MSB]

CRC: CRC-16/KERMIT  (poly=0x1021, init=0x0000, refIn=True, refOut=True, xorOut=0x0000)
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))

import time
import threading
import logging

import serial_manager as sm

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRC-16/KERMIT
# ---------------------------------------------------------------------------

def crc16_kermit(data: bytes) -> int:
    """CRC-16/KERMIT: poly=0x1021 reflected, init=0x0000, xorOut=0x0000."""
    crc = 0x0000
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408  # 0x1021 reversed
            else:
                crc >>= 1
    return crc & 0xFFFF


# ---------------------------------------------------------------------------
# Command IDs
# ---------------------------------------------------------------------------

class CmdFTM:
    """FTM command codes (header 0x0E)."""
    GET_BT_INFO          = 0x00
    GET_TACTILE_INFO     = 0x01
    GET_HAPTIC_INFO      = 0x02
    GET_COULOMB_INFO     = 0x03
    BLUETOOTH_BURST      = 0x04
    TACTILE_SENSOR_READ  = 0x05
    HAPTIC_VIBRATING     = 0x06
    COULOMB_COUNTER_READ = 0x07
    LED_ACTION_RGB       = 0x08
    LED_POWER_RGB        = 0x09
    LIGHTBAR_PULSING     = 0x0A
    BUZZER_PLAYING       = 0x0B
    IMU_READ             = 0x0C
    WATCHDOG_RESET       = 0x0D
    BT_RF_SIG            = 0x0E
    CHARGING_INFO        = 0x0F
    TESTING_ALL          = 0x10
    STOP                 = 0x11


class CmdID:
    """Command frame IDs (setiap message punya header byte sendiri)."""
    CONFIG_REQUEST       = 0x00
    START_STREAMING      = 0x01
    CLICK_MESSAGE        = 0x02
    SAVE_TUNNING         = 0x03
    LED_BAR_TUNNING      = 0x04
    BATTERY_REQUEST      = 0x05
    FORCE_IDLE           = 0x06
    BATTERY_INDICATION   = 0x07
    LED_BAR              = 0x08
    HAPTIC_FEEDBACK      = 0x09
    CALIBRATION_WRITE    = 0x0A
    CALIBRATION_READ     = 0x0B
    FUOTA_START          = 0x0C  # (shared header with FUOTA frame)
    ACK                  = 0xFF


# ---------------------------------------------------------------------------
# BexaResponse
# ---------------------------------------------------------------------------

class BexaResponse:
    """Hasil dari satu transaksi ke Bexa."""

    def __init__(self, valid: bool, status: int = 0,
                 payload: bytes = b"", error: str = ""):
        self.valid   = valid
        self.status  = status    # 0 = OK dari device
        self.payload = payload
        self.error   = error

    def __repr__(self):
        return (f"BexaResponse(valid={self.valid}, status=0x{self.status:02X}, "
                f"payload={self.payload.hex()}, error={self.error!r})")


# ---------------------------------------------------------------------------
# BexaCommand — base class
# ---------------------------------------------------------------------------

class BexaCommand:
    """
    Base class untuk semua command Bexa.

    Komunikasi via Bluetooth Classic SPP yang didaftarkan
    sebagai koneksi 'bluetooth' di serial_manager.
    """

    CONN    = "bluetooth"   # nama koneksi di config.json
    TIMEOUT = 5.0           # detik — aktuator (haptic, LED) butuh waktu lebih

    # Header bytes
    _HDR_FTM = 0x0E
    _HDR_ACK = 0xFF

    def __init__(self, conn: str = None, timeout: float = None, params=None):
        self._conn    = conn    or self.CONN
        self._timeout = timeout or self.TIMEOUT

    # ------------------------------------------------------------------ build

    def _build_ftm_frame(self, cmd: int, tid: int = 0x00) -> bytes:
        """
        Build FTM request frame.
        [0x0E][LEN_LSB][LEN_MSB][TID][CMD][CRC_LSB][CRC_MSB]
        """
        body   = bytes([tid, cmd])
        length = len(body)
        raw    = bytes([self._HDR_FTM, length & 0xFF, (length >> 8) & 0xFF]) + body
        crc    = crc16_kermit(raw)
        return raw + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    def _build_cmd_frame(self, cmd_id: int, payload: bytes = b"",
                         tid: int = 0x00) -> bytes:
        """
        Build Command request frame.
        [CMD_ID][LEN_LSB][LEN_MSB][TID][PAYLOAD...][CRC_LSB][CRC_MSB]
        """
        body   = bytes([tid]) + payload
        length = len(body)
        raw    = bytes([cmd_id, length & 0xFF, (length >> 8) & 0xFF]) + body
        crc    = crc16_kermit(raw)
        return raw + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    # ------------------------------------------------------------------ parse

    def _parse_ack(self, data: bytes) -> BexaResponse:
        """
        Parse ACK frame dari Bexa.
        [0xFF][LEN_LSB][LEN_MSB][TID][MSG_ID][STATUS][PAYLOAD_PRESENT]
        [PL_LEN_LSB][PL_LEN_MSB][PAYLOAD...][CRC_LSB][CRC_MSB]
        """
        if len(data) < 7:
            return BexaResponse(False, error=f"Response terlalu pendek ({len(data)} bytes)")
        if data[0] != self._HDR_ACK:
            return BexaResponse(False, error=f"Header tidak valid: 0x{data[0]:02X}")

        length = data[1] | (data[2] << 8)
        total  = 3 + length + 2     # header(3) + body(length) + crc(2)
        if len(data) < total:
            return BexaResponse(False, error=f"Data tidak lengkap ({len(data)}/{total})")

        # Validasi CRC
        raw_for_crc = data[:3 + length]
        crc_recv    = data[3 + length] | (data[3 + length + 1] << 8)
        crc_calc    = crc16_kermit(raw_for_crc)
        if crc_recv != crc_calc:
            return BexaResponse(False,
                error=f"CRC error (calc=0x{crc_calc:04X}, recv=0x{crc_recv:04X})")

        body = data[3:3 + length]
        # body: [TID][MSG_ID][STATUS][PAYLOAD_PRESENT][PL_LEN_LSB][PL_LEN_MSB][PAYLOAD...]
        if len(body) < 3:
            return BexaResponse(False, error="Body terlalu pendek")

        status          = body[2]
        payload_present = body[3] if len(body) > 3 else 0
        payload         = b""

        if payload_present and len(body) >= 6:
            pl_len  = body[4] | (body[5] << 8)
            payload = body[6:6 + pl_len]

        if status != 0:
            return BexaResponse(False, status=status,
                error=f"Device error status=0x{status:02X}")

        return BexaResponse(True, status=status, payload=payload)

    # ------------------------------------------------------------------ xfer

    def xfer_ftm(self, cmd: int, timeout: float = None) -> BexaResponse:
        """Kirim FTM frame, tunggu dan parse ACK response."""
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            return BexaResponse(False,
                error=f"Koneksi '{self._conn}' tidak terhubung")

        frame = self._build_ftm_frame(cmd)
        tmo   = timeout or self._timeout

        try:
            port = comm._port
            port.reset_input_buffer()
            port.write(frame)
            _log.debug("[BEXA] TX FTM 0x%02X: %s", cmd, frame.hex())
        except Exception as e:
            return BexaResponse(False, error=f"Write error: {e}")

        # Baca sampai dapat frame ACK lengkap
        buf = bytearray()
        t0  = time.monotonic()
        while (time.monotonic() - t0) < tmo:
            try:
                waiting = port.in_waiting
            except Exception:
                waiting = 0
            if waiting:
                buf.extend(port.read(waiting))
                _log.debug("[BEXA] RX partial (%d bytes): %s", len(buf), buf.hex())
                # Cari header ACK
                idx = buf.find(bytes([self._HDR_ACK]))
                if idx > 0:
                    del buf[:idx]   # buang bytes sebelum header
                if len(buf) >= 3:
                    length = buf[1] | (buf[2] << 8)
                    needed = 3 + length + 2
                    if len(buf) >= needed:
                        _log.debug("[BEXA] RX complete: %s", bytes(buf[:needed]).hex())
                        return self._parse_ack(bytes(buf[:needed]))
            else:
                time.sleep(0.005)

        return BexaResponse(False, error="Timeout menunggu respons ACK")

    def xfer_cmd(self, cmd_id: int, payload: bytes = b"",
                 timeout: float = None) -> BexaResponse:
        """Kirim Command frame, tunggu dan parse ACK response."""
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            return BexaResponse(False,
                error=f"Koneksi '{self._conn}' tidak terhubung")

        frame = self._build_cmd_frame(cmd_id, payload)
        tmo   = timeout or self._timeout

        try:
            port = comm._port
            port.reset_input_buffer()
            port.write(frame)
            _log.debug("[BEXA] TX CMD 0x%02X: %s", cmd_id, frame.hex())
        except Exception as e:
            return BexaResponse(False, error=f"Write error: {e}")

        buf = bytearray()
        t0  = time.monotonic()
        while (time.monotonic() - t0) < tmo:
            try:
                waiting = port.in_waiting
            except Exception:
                waiting = 0
            if waiting:
                buf.extend(port.read(waiting))
                idx = buf.find(bytes([self._HDR_ACK]))
                if idx > 0:
                    del buf[:idx]
                if len(buf) >= 3:
                    length = buf[1] | (buf[2] << 8)
                    needed = 3 + length + 2
                    if len(buf) >= needed:
                        return self._parse_ack(bytes(buf[:needed]))
            else:
                time.sleep(0.005)

        return BexaResponse(False, error="Timeout menunggu respons ACK")

    def execute(self) -> str:
        raise NotImplementedError
