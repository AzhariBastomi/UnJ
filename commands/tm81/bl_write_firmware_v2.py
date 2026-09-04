"""
commands/tm81/bl_write_firmware_v2.py — OTA Flash via IrDA (TM81 Bootloader) v2

Sama dengan bl_write_firmware.py tapi tambah resume support:
- Sebelum BL_SET_RDY, query BL_GET_OTA_PROGRESS (cmd 106)
- Jika device punya state OTA yang match (size + CRC), lanjut dari frame terakhir
- Jika tidak match atau tidak ada, mulai fresh (SET_RDY + semua chunk)

BL_GOTO_APP tidak dikirim dari sini — dihandle oleh step bl_goto_app tersendiri di flow OTA2.
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

_NO_FRAME = 0xFFFF   # nilai last_frame_id jika belum ada frame yang tersimpan


class BLWriteFirmwareV2(TM81Command):
    CHUNK_SIZE   = 512
    FILL_WITH_FF = False
    APP_MAX_SIZE = 1024 * 160   # 160 KB

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._fw_path      = p.get("fw_path", "")
        self._chunk_size   = p.get("chunk_size",   self.CHUNK_SIZE)
        self._fill_with_ff = p.get("fill_with_ff", self.FILL_WITH_FF)
        self._progress_cb  = p.get("progress_cb",  None)

    def _resolve_fw_path(self) -> str:
        if self._fw_path:
            return self._fw_path
        try:
            import json as _json
            _cfg_path = os.path.join(
                os.path.dirname(__file__), "config", "tm81_ota2.json"
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
        self._fw_path = fw_path

        with open(self._fw_path, "rb") as f:
            fw_data = f.read(self.APP_MAX_SIZE)

        fw_size   = len(fw_data)
        crc_bytes = Crc32Mpeg2.calc(fw_data).to_bytes(4, "little")
        file_crc  = int.from_bytes(crc_bytes, "little")

        if self._fill_with_ff and fw_size < self.APP_MAX_SIZE:
            fw_data += b"\xff" * (self.APP_MAX_SIZE - fw_size)

        _log.debug("  FW: %s", os.path.basename(self._fw_path))
        _log.debug("  Size: %d B  CRC: %s", fw_size, crc_bytes.hex(" "))

        try:
            from controllers.keepalive import pause_global, resume_global
            _ka = True
        except ImportError:
            _ka = False

        if _ka:
            pause_global()
            _log.debug("  [BLWrite v2] keepalive paused")

        try:
            total_frames = (fw_size + self._chunk_size - 1) // self._chunk_size

            # ── Resume check ──────────────────────────────────────────────────
            start_frame = 0
            ok, dev_size, dev_crc, dev_last = self._get_ota_progress()

            if not ok:
                # Cmd 106 timeout — bootloader lama tidak support cmd 106,
                # atau koneksi belum stabil. Lanjut fresh transfer.
                _log.debug(
                    "  OTA progress timeout — bootloader tidak support cmd 106 "
                    "atau koneksi tidak stabil. Lanjut fresh transfer."
                )
                r_clr = self._bl_clear_ota()
                if r_clr != "OK":
                    _log.debug("  BL_OTA_CLEAR gagal (%s) — tetap lanjut fresh transfer", r_clr)
                r = self._bl_set_rdy(fw_size, crc_bytes)
                if r != "OK":
                    return r
                time.sleep(0.5)
            else:
                resume = (
                    dev_size == fw_size
                    and dev_crc  == file_crc
                    and dev_last != _NO_FRAME
                    and 0 <= dev_last < total_frames
                )
                if resume:
                    start_frame = dev_last + 1
                    _log.debug(
                        "  RESUME dari frame %d (device last=%d, size=%d, crc=0x%08X)",
                        start_frame, dev_last, dev_size, dev_crc
                    )
                    # Set progress bar ke posisi resume agar tidak terlihat
                    # mulai dari 0% padahal chunk sudah dikirim sebagian.
                    resume_pct = min((start_frame * self._chunk_size) / fw_size * 100, 99)
                    if self._progress_cb:
                        self._progress_cb(int(resume_pct))
                else:
                    # Cmd 106 berhasil tapi last_frame=0xFFFF atau size/CRC beda
                    # → clear metadata dulu, lalu erase flash dan mulai fresh
                    _log.debug(
                        "  FRESH TRANSFER — last_frame=%d size_match=%s crc_match=%s",
                        dev_last, dev_size == fw_size, dev_crc == file_crc
                    )
                    # Bersihkan metadata OTA lama sebelum erase — antisipasi sisa
                    # CRC/size dari sesi sebelumnya yang bisa bikin bootloader bingung
                    r_clr = self._bl_clear_ota()
                    if r_clr != "OK":
                        _log.debug("  BL_OTA_CLEAR gagal (%s) — tetap lanjut fresh transfer", r_clr)
                    r = self._bl_set_rdy(fw_size, crc_bytes)
                    if r != "OK":
                        return r
                    time.sleep(0.5)

            # ── Kirim chunk ───────────────────────────────────────────────────
            r = self._bl_send_chunks(fw_data, start_frame=start_frame)
            if r != "OK":
                return r

            # BL_GOTO_APP dihandle oleh step bl_goto_app yang terpisah di flow OTA2
            return "OK"

        finally:
            if _ka:
                resume_global()
                _log.debug("  [BLWrite v2] keepalive resumed")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_ota_progress(self, retries: int = 4, retry_delay: float = 0.8) -> tuple:
        """Query BL_GET_OTA_PROGRESS. Return (ok, fw_size, fw_crc, last_frame_id).

        Retry beberapa kali karena IrDA yang baru reconnect butuh waktu stabilisasi.
        """
        for attempt in range(retries):
            if attempt > 0:
                _log.debug("  OTA progress retry %d/%d ...", attempt + 1, retries - 1)
                time.sleep(retry_delay)
            result = self.xfer(CmdId.BL_GET_OTA_PROGRESS, timeout=2.0)
            if result.valid and len(result.payload) >= 10:
                p = result.payload
                fw_size    = int.from_bytes(p[0:4], "little")
                fw_crc     = int.from_bytes(p[4:8], "little")
                last_frame = int.from_bytes(p[8:10], "little")
                _log.debug("  OTA progress: size=%d crc=0x%08X last_frame=%d", fw_size, fw_crc, last_frame)
                return (True, fw_size, fw_crc, last_frame)
            _log.debug(
                "  OTA progress attempt %d/%d: %s "
                "(kemungkinan: bootloader lama tidak support cmd 106, "
                "atau IrDA belum stabil)",
                attempt + 1, retries, result.error
            )
        _log.debug(
            "  OTA progress tidak tersedia setelah %d percobaan "
            "(cmd 106 selalu timeout). Kemungkinan penyebab: "
            "(1) bootloader lama belum support cmd 106, "
            "(2) device belum masuk mode Bootloader, "
            "(3) koneksi IrDA tidak stabil. Lanjut fresh transfer.",
            retries
        )
        return (False, 0, 0, _NO_FRAME)

    def _bl_clear_ota(self) -> str:
        """Kirim BL_OTA_CLEAR (cmd 107) untuk reset metadata OTA di EEPROM."""
        result = self.xfer(CmdId.BL_OTA_CLEAR, timeout=3.0)
        if not result.valid and result.error not in ("ACK",):
            _log.debug(
                "  BL_OTA_CLEAR (cmd 107) gagal: %s "
                "(kemungkinan: bootloader lama belum support cmd 107, "
                "atau koneksi IrDA tidak stabil — diabaikan, lanjut)",
                result.error
            )
            return f"NG:{result.error}"
        _log.debug("  BL_OTA_CLEAR → ACK — metadata OTA di EEPROM berhasil direset")
        return "OK"

    def _bl_set_rdy(self, fw_size: int, crc_bytes: bytes) -> str:
        data   = fw_size.to_bytes(4, "little") + crc_bytes
        result = self.xfer(CmdId.BL_SET_RDY, data, timeout=8.0)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:BL_SET_RDY {result.error}"
        _log.debug("  BL_SET_RDY → ACK")
        return "OK"

    def _bl_send_chunks(self, fw_data: bytes, start_frame: int = 0,
                        chunk_retries: int = 2) -> str:
        total       = len(fw_data)
        chunk_size  = self._chunk_size
        i           = start_frame * chunk_size
        frame_id    = start_frame
        total_frames = (total + chunk_size - 1) // chunk_size

        if i >= total:
            # Semua frame sudah terkirim sebelumnya (last_frame = frame terakhir),
            # tapi BL_GOTO_APP belum sempat dipanggil. Langsung return OK agar
            # caller (execute) bisa lanjut ke BL_GOTO_APP.
            _log.debug("  Resume: semua %d frame sudah terkirim (offset %d >= size %d), skip transfer",
                       total_frames, i, total)
            if self._progress_cb:
                self._progress_cb(100)
            return "OK"

        while i < total:
            chunk     = fw_data[i: i + chunk_size]
            chunk_len = len(chunk)
            payload   = (
                frame_id.to_bytes(2, "little")
                + chunk_len.to_bytes(2, "little")
                + chunk
            )

            # Log sebelum kirim: frame ke-N dari total, byte offset
            _log.debug("  [TX] frame %d/%d  offset=%d-%d  (%dB)",
                       frame_id, total_frames - 1,
                       i, i + chunk_len - 1, chunk_len)

            # Kirim dengan retry per-frame
            result = None
            for attempt in range(chunk_retries + 1):
                if attempt > 0:
                    _log.debug("  [RETRY] frame %d — attempt %d/%d",
                               frame_id, attempt, chunk_retries)
                result = self.xfer(CmdId.BL_FW_DATA, payload, timeout=3.0)
                if result.valid or result.error in ("ACK",):
                    break

            if not result.valid and result.error not in ("ACK",):
                return f"NG:BL_FW_DATA frame={frame_id}/{total_frames - 1} {result.error}"

            i        += chunk_len
            frame_id += 1
            pct       = i / total * 100
            _log.debug("  [ACK] frame %d/%d  %.1f%%",
                       frame_id - 1, total_frames - 1, pct)

            if self._progress_cb:
                self._progress_cb(pct)

        _log.debug("  Semua %d frame terkirim", frame_id)
        return "OK"

