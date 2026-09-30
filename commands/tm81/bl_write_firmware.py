"""
commands/tm81/bl_write_firmware.py — OTA Flash via IrDA (TM81 Bootloader)

Flow OTA:
  1. BL_SET_RDY — kirim fw_size (4B LE) + CRC32-MPEG2 (4B LE)
  2. BL_FW_DATA — kirim data chunk per chunk (frame_id + chunk_size + data)

BL_GOTO_APP tidak dikirim dari sini — dihandle oleh step bl_goto_app tersendiri di flow OTA.
progress_cb(float 0-100) dipanggil setiap chunk selesai dikirim.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))

import os
import time
from crccheck.crc import Crc32Mpeg2
import logging
_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

from commands.tm81.bl_tools import fw_max_size, check_fw_size


class BLWriteFirmware(TM81Command):

    RETRIES = 1   # retry per chunk sudah diatur sendiri
    CHUNK_SIZE   = 512          # bytes per frame — override via params
    FILL_WITH_FF = False        # pad file ke APP_MAX_SIZE dengan 0xFF
    APP_MAX_SIZE = 1024 * 160   # 160 KB

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._fw_path      = p.get("fw_path", "")
        self._chunk_size   = p.get("chunk_size",   self.CHUNK_SIZE)
        self._fill_with_ff = p.get("fill_with_ff", self.FILL_WITH_FF)
        # "app" (default) atau "bl" — suite tm81_ota_bl di-set "bl" oleh loader
        self._region       = str(p.get("region", "app")).lower()
        self._progress_cb  = p.get("progress_cb",  None)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def _resolve_fw_path(self) -> str:
        """Jika fw_path kosong, baca dari tm81_ota.json saat runtime."""
        if self._fw_path:
            return self._fw_path
        try:
            import json as _json
            _cfg_path = os.path.join(
                os.path.dirname(__file__), "config", "tm81_ota.json"
            )
            with open(_cfg_path, encoding="utf-8") as f:
                cfg = _json.load(f)
            fw_ver = cfg.get("fw_version", "")
            if fw_ver and os.path.isabs(fw_ver):
                return fw_ver
            fw_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "firmware"
            )
            return os.path.join(fw_dir, fw_ver) if fw_ver else ""
        except Exception:
            return ""

    def execute(self) -> str:
        fw_path = self._resolve_fw_path()
        if not fw_path or not os.path.isfile(fw_path):
            return f"NG:File tidak ditemukan: {fw_path!r}"
        self._fw_path = fw_path  # simpan agar log benar

        size_err = check_fw_size(self._fw_path, self._region)
        if size_err:
            return size_err
        max_size = fw_max_size(self._region)

        # Baca firmware
        with open(self._fw_path, "rb") as f:
            fw_data = f.read(max_size)

        fw_size   = len(fw_data)
        crc_bytes = Crc32Mpeg2.calc(fw_data).to_bytes(4, "little")

        if self._fill_with_ff and fw_size < max_size:
            fw_data += b"\xff" * (max_size - fw_size)

        _log.debug("  FW: %s", os.path.basename(self._fw_path))
        _log.debug("  Size: %d B  CRC: %s", fw_size, crc_bytes.hex(" "))

        # ── Pause keepalive ping (safety layer ke-2) ──────────────────────────
        # Layer pertama: _TM81FlashStep.run() di test_loader.py.
        # Layer ini menjamin ping TIDAK masuk bahkan jika BLWriteFirmware
        # dipanggil langsung (standalone / path lain), sekaligus menunggu
        # ping yang sedang berjalan selesai sebelum mulai kirim ke bootloader.
        try:
            from controllers.keepalive import pause_global, resume_global
            _ka = True
        except ImportError:
            _ka = False

        if _ka:
            pause_global()
            _log.debug("  [BLWrite] keepalive paused")

        try:
            # Step 1: BL_SET_RDY — kirim fw_size + CRC
            r = self._bl_set_rdy(fw_size, crc_bytes)
            if r != "OK":
                return r
            time.sleep(0.5)

            # Step 2: BL_FW_DATA — kirim chunk per chunk
            r = self._bl_send_chunks(fw_data)
            if r != "OK":
                return r

            # BL_GOTO_APP dihandle oleh step bl_goto_app yang terpisah di flow OTA
            return "OK"

        finally:
            if _ka:
                resume_global()
                _log.debug("  [BLWrite] keepalive resumed")

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _bl_set_rdy(self, fw_size: int, crc_bytes: bytes) -> str:
        data = fw_size.to_bytes(4, "little") + crc_bytes
        result = self.xfer(CmdId.BL_SET_RDY, data, timeout=8.0)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:BL_SET_RDY {result.error}"
        _log.debug("  BL_SET_RDY → ACK")
        return "OK"

    def _bl_send_chunks(self, fw_data: bytes) -> str:
        total      = len(fw_data)
        chunk_size = self._chunk_size
        sent       = 0
        frame_id   = 0

        while sent < total:
            chunk     = fw_data[sent: sent + chunk_size]
            chunk_len = len(chunk)
            payload   = (
                frame_id.to_bytes(2, "little")
                + chunk_len.to_bytes(2, "little")
                + chunk
            )

            result = self.xfer(CmdId.BL_FW_DATA, payload, timeout=3.0)
            if not result.valid and result.error not in ("ACK",):
                return f"NG:BL_FW_DATA frame={frame_id} {result.error}"

            sent     += chunk_len
            frame_id += 1
            pct       = sent / total * 100
            _log.debug("  [%d] %d/%d B  %.1f%%", frame_id, sent, total, pct)

            if self._progress_cb:
                self._progress_cb(pct)

        _log.debug(f"  Semua {frame_id} chunk terkirim")
        return "OK"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    import sys
    fw_path = sys.argv[1] if len(sys.argv) > 1 else "firmware.bin"
    params = {"firmware_path": fw_path}
    result = BLWriteFirmware(params=params).execute()
    print(result)
    sm.disconnect_all()
