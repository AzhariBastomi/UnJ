"""
commands/tm81/bl_tools.py — Helper OTA untuk TM81 Bootloader

Berisi fungsi-fungsi reusable untuk:
- Query OTA progress dari device (cmd 106)
- Cek apakah OTA image sudah lengkap

Digunakan oleh: bl_write_firmware_v2.py, bl_goto_app.py, bl_clear_ota.py
"""

import logging
import os
_log = logging.getLogger(__name__)

# Batas ukuran image OTA per region — sama dengan SWM Lib/Env.py
# (AppConstants.FW_APP_MAX_SIZE / FW_BOOTLOADER_MAX_SIZE).
APP_MAX_SIZE = 1024 * 160   # 160 KB
BL_MAX_SIZE  = 1024 * 32    # 32 KB


def fw_max_size(region: str) -> int:
    """Batas ukuran image untuk region OTA ("app" / "bl")."""
    return BL_MAX_SIZE if str(region or "app").lower() == "bl" else APP_MAX_SIZE


def check_fw_size(fw_path: str, region: str) -> "str | None":
    """Tolak file yang lebih besar dari batas region (mis. file App dipilih
    di suite OTA Bootloader). Return pesan NG, atau None kalau aman.
    Dulu file dipotong diam-diam ke 160 KB tanpa peringatan."""
    size  = os.path.getsize(fw_path)
    limit = fw_max_size(region)
    if size > limit:
        reg = "BOOTLOADER" if limit == BL_MAX_SIZE else "APP"
        return (f"NG:{os.path.basename(fw_path)} = {size} B melebihi batas region "
                f"{reg} ({limit} B) — salah pilih file firmware?")
    return None

_NO_FRAME   = 0xFFFF   # sentinel: belum ada frame yang tersimpan di EEPROM
_CHUNK_SIZE = 512      # ukuran per frame OTA (harus sama dengan BLWriteFirmwareV2.CHUNK_SIZE)

try:
    from commands.tm81.base import CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    from commands.tm81.base import CmdId


def get_ota_progress(cmd_obj, timeout: float = 2.0) -> tuple:
    """Query BL_GET_OTA_PROGRESS (cmd 106) ke device.

    Args:
        cmd_obj: instance TM81Command (atau subclass) yang sudah terhubung.
        timeout: timeout per percobaan (detik).

    Returns:
        (ok, fw_size, fw_crc, last_frame_id)
        - ok=True  → query berhasil, nilai lain valid
        - ok=False → timeout / payload terlalu pendek, nilai lain = 0 / NO_FRAME
    """
    result = cmd_obj.xfer(CmdId.BL_GET_OTA_PROGRESS, timeout=timeout)
    if result.valid and len(result.payload) >= 10:
        p          = result.payload
        fw_size    = int.from_bytes(p[0:4], "little")
        fw_crc     = int.from_bytes(p[4:8], "little")
        last_frame = int.from_bytes(p[8:10], "little")
        _log.debug("  [OTA progress] size=%d crc=0x%08X last_frame=%d", fw_size, fw_crc, last_frame)
        return (True, fw_size, fw_crc, last_frame)

    _log.debug("  [OTA progress] gagal: %s", result.error)
    return (False, 0, 0, _NO_FRAME)


def is_ota_image_complete(fw_size: int, last_frame_id: int,
                          chunk_size: int = _CHUNK_SIZE) -> bool:
    """True jika semua frame OTA sudah tertulis di flash.

    Mirrors logika bootloader boot_is_app_image_valid():
    last_frame_id adalah frame terakhir yang berhasil diprogram secara berurutan,
    sehingga (last_frame_id + 1) * chunk_size harus mencakup fw_size.

    NO_FRAME (0xFFFF) berarti belum ada frame yang ditulis setelah erase.
    """
    if fw_size <= 0 or fw_size >= 0xFFFFFFFF:
        return False
    if last_frame_id == _NO_FRAME:
        return False
    frames_written = last_frame_id + 1
    frames_needed  = (fw_size + chunk_size - 1) // chunk_size
    return frames_written >= frames_needed
