"""
commands/tm81/base.py - Base class untuk semua command TM81.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

import logging
import threading
import serial_manager as sm
from serial_comm import TM81Parser, ParseResult

_xlog = logging.getLogger(__name__)

# Byte status yang dikirim device DI DALAM frame (payload 1 byte), mis.
#   01 0f 00 0c 02 [11] 03 <crc> 04   -> ACK
# Referensi: SWM_Test_Scripts/Lib/Env.py (SerialConstants.ACK_INT / NAK_INT)
_FRAMED_ACK = 0x11
_FRAMED_NAK = 0x0F
_HEADER_PREFIX = b"\x01\x0f"


class CmdId:
    PING                    = 0x00
    IRDA_DISABLE            = 0x01
    SENSOR_GET_CONFIG       = 0x02
    SENSOR_RESET_CONFIG     = 0x03
    SENSOR_GET_DATA         = 0x04
    USR_REBOOT_BOOTLOADER   = 0x05
    USR_SYNC_CFG            = 0x06
    USR_SET_CFG             = 0x07
    USR_GET_CONFIG          = 0x08
    USR_RESET_CONFIG        = 0x09
    USR_GET_TIME            = 0x0A
    USR_SET_TIME            = 0x0B
    USR_GET_VER             = 0x0C
    USR_TEST_WDT            = 0x0D
    ENTER_STANDBY           = 0x0E
    SET_DEV_EUI             = 0x0F
    SET_JOIN_EUI            = 0x10
    SET_APP_KEY             = 0x11
    SET_NW_KEY              = 0x12
    SET_DEV_ADDR            = 0x13
    SET_JOIN_MODE           = 0x14
    SET_DEV_CLASS           = 0x15
    GET_LORA_DATA           = 0x16
    FORCE_SEND_LORA         = 0x17
    USAGE_HISTORY_READ      = 0x18
    USAGE_HISTORY_WRITE     = 0x19
    GET_DEV_INFO            = 0x1A
    DEV_GET_ID              = 0x1B
    DEV_SET_ID              = 0x1C
    SET_LORA_DATA           = 0x1D
    TEST_GET_CHIP_ID        = 0x1E
    TEST_CC_GET_TEMP        = 0x1F
    TEST_CC_RESET_ACR       = 0x20
    TEST_CC_GET_ACR         = 0x21
    TEST_SOFT_RESET         = 0x22
    GET_LAST_SUBMIT_TIME    = 0x23
    RESET_BATTERY_CONFIG    = 0x24
    SET_LORA_ADR            = 0x25
    BL_SET_RDY              = 100
    BL_FW_DATA              = 101
    BL_GOTO_APP             = 102
    BL_GET_OTA_PROGRESS     = 106
    BL_OTA_CLEAR            = 107
    BL_GO_TO_BL             = 103
    BL_GET_SESSION          = 108
    USR_FACTORY_RESET       = 109
    EEPROM_PAGE_READ        = 110


class TM81Command:
    """Base class untuk semua command TM81."""

    CONN    = "ch340"
    TIMEOUT = 2.0
    # Jumlah percobaan kirim kalau TIDAK ada frame balasan (timeout / byte
    # sampah seperti 0xE3). Sama dengan SWM (SerialConstants.MAX_RETRY = 3).
    # NAK TIDAK di-retry — itu penolakan yang disengaja dari firmware.
    # Command yang tidak boleh terkirim dua kali (reset, jump, knock, dst)
    # override RETRIES = 1 di class-nya.
    RETRIES = 3

    def __init__(self, conn: str = None, timeout: float = None, params=None,
                 retries: int = None):
        self._conn    = conn    or self.CONN
        self._timeout = timeout or self.TIMEOUT
        self._retries = retries if retries is not None else self.RETRIES

    @staticmethod
    def _normalize_framed_status(pr: ParseResult) -> ParseResult:
        """Frame berisi payload 1 byte 0x11/0x0F = ACK/NAK dari firmware.

        Parser hanya mengenali ACK/NAK sebagai byte mentah; yang dikirim di
        dalam frame dulu dianggap "payload valid" sehingga NAK ikut lolos
        sebagai OK. Di sini disamakan dengan ACK/NAK mentah.
        """
        if (pr.valid and not pr.error and len(pr.payload) == 1
                and pr.raw[:2] == _HEADER_PREFIX):
            status = pr.payload[0]
            if status == _FRAMED_ACK:
                return ParseResult(raw=pr.raw, payload=b"", valid=True, error="ACK")
            if status == _FRAMED_NAK:
                return ParseResult(raw=pr.raw, payload=b"", valid=False, error="NAK")
        return pr

    def xfer(self, cmd_id: int, data: bytes = b"", timeout: float = None,
             retries: int = None) -> ParseResult:
        comm = sm.get_comm(self._conn)
        if comm is None or not comm.is_connected():
            return ParseResult(raw=b"", payload=b"", valid=False,
                               error=f"Koneksi '{self._conn}' tidak terhubung")

        timeout  = timeout or self._timeout
        attempts = max(1, int(retries if retries is not None else self._retries))

        # Acquire per-connection lock — satu transaksi (send+receive) selesai dulu
        # sebelum thread lain (keepalive ping atau test command lain) boleh kirim.
        # Tidak ada pause/resume manual yang diperlukan; siapapun yang coba xfer()
        # saat port sedang dipakai cukup menunggu di sini.
        lock = sm.get_lock(self._conn)
        pr   = None
        with lock:
            for attempt in range(1, attempts + 1):
                # Bersihkan sisa bytes dari response sebelumnya agar ACK detection
                # tidak terganggu leftover di parser buffer (mis. tail frame setelah \x11).
                comm._parser._buf.clear()
                try:
                    comm._port.reset_input_buffer()
                except Exception:
                    pass

                frame  = comm._parser.build_send_frame(cmd_id, data)
                result = [None]
                event  = threading.Event()

                def _on_data(r: ParseResult, _res=result, _ev=event):
                    # Frame balasan membawa cmd id di byte [2] (01 0f CMD LEN 02).
                    # Abaikan frame milik command lain (sisa transaksi sebelumnya)
                    # — sama seperti SWM yang mencocokkan prefix cmd+len.
                    if (r.valid and len(r.raw) >= 3 and r.raw[:2] == _HEADER_PREFIX
                            and r.raw[2] != cmd_id):
                        _xlog.debug("[xfer] abaikan frame cmd=0x%02x (menunggu 0x%02x)",
                                   r.raw[2], cmd_id)
                        return
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
                if pr is not None:
                    break
                if attempt < attempts:
                    _xlog.debug("[xfer] cmd=0x%02x timeout — retry %d/%d",
                               cmd_id, attempt + 1, attempts)

            if pr is None:
                pr = ParseResult(raw=b"", payload=b"", valid=False, error="Timeout")

        pr = self._normalize_framed_status(pr)

        # Log hasil parsing ke serial_comm logger agar tampil di CH340 debug window
        _log = getattr(comm._parser, "_log", None)
        if _log is not None:
            if not pr.valid:
                _log.debug("[TM81 RESULT] NG  error=%r", pr.error)
            elif pr.error == "ACK":
                _log.debug("[TM81 RESULT] OK  ACK (no payload)")
            else:
                plen = len(pr.payload)
                phex = pr.payload.hex(" ") if plen else "—"
                _log.debug("[TM81 RESULT] OK  payload(%dB): %s", plen, phex)

        return pr

    def execute(self) -> str:
        raise NotImplementedError
