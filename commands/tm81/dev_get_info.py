"""
commands/tm81/dev_get_info.py — Get Device Info (CMD 0x1A)
Response payload (20 bytes):
  [0]    Sensor Intensity
  [1]    Sensor Indication
  [2-3]  Battery INTP (big-endian)
  [4-5]  Battery Impedance (mOhm)
  [6-7]  Battery Usage (mAh)
  [8-9]  Battery Capacity Remaining (mAh)
  [10]   Battery Percentage
  [11-14] LoRaWAN Network ID (little-endian → big-endian hex)
  [15]   Last Downlink RSSI (signed)
  [16]   Last Downlink SNR (signed)
  [17]   Is in Join/Uplink Session
  [18]   Is Ever Joined
  [19]   Is Last Uplink Success
  [20]   Is Last Uplink in Retry      (firmware baru, payload 22 byte)
  [21]   Last Uplink Retry Count      (firmware baru, payload 22 byte)
  [22]   Init Status bitmask          (firmware baru, payload 23 byte)
  [23-26] Remaining Power Recovery Time, detik (firmware baru, payload 27 byte)

Firmware lama mengirim 20 byte — byte 20 ke atas hanya dibaca kalau ada.
Referensi: SWM_Test_Scripts/Src/DevGetInfo.py
"""

import logging
_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class DevGetInfo(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.GET_DEV_INFO)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 20:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        def signed(b):
            return b if b < 128 else b - 256

        info = {
            "sensor_intensity":         d[0],
            "sensor_indication":        d[1],
            "battery_intp":             d[3] | (d[2] << 8),
            "battery_impedance_mohm":   d[5] | (d[4] << 8),
            "battery_usage_mah":        d[6] | (d[7] << 8),
            "battery_remaining_mah":    d[8] | (d[9] << 8),
            "battery_pct":              d[10],
            "lorawan_network_id":       int.from_bytes(d[11:15], "little").to_bytes(4, "big").hex(),
            "last_dl_rssi_dbm":         signed(d[15]),
            "last_dl_snr_db":           signed(d[16]),
            "in_join_session":          bool(d[17]),
            "ever_joined":              bool(d[18]),
            "last_uplink_success":      bool(d[19]),
        }
        has_retry = len(d) >= 22
        if has_retry:
            info["last_uplink_in_retry"]    = bool(d[20])
            info["last_uplink_retry_count"] = d[21]
        has_init = len(d) >= 23
        if has_init:
            info["init_status"]        = d[22]
            info["init_failed_steps"]  = self._init_failed_steps(d[22])
        has_recovery = len(d) >= 27
        if has_recovery:
            info["recovery_remaining_min"] = int.from_bytes(d[23:27], "little") / 60

        self._last_payload = d
        self._last_info = info
        for k, v in info.items():
            _log.debug(f"  {k}: {v}")

        # Baris pertama = summary singkat (tampil di row UI)
        joined_str = "Yes" if info["ever_joined"] else "No"
        ul_str     = "Yes" if info["last_uplink_success"] else "No"
        summary = (
            f"Bat: {info['battery_pct']}% | "
            f"RSSI: {info['last_dl_rssi_dbm']} dBm | "
            f"Joined: {joined_str}"
        )

        # Detail (tampil saat di-klik) — satu field per baris
        detail = "\n".join([
            f"Sensor Intensity   : {info['sensor_intensity']}",
            f"Sensor Indication  : {info['sensor_indication']}",
            f"Battery Percentage : {info['battery_pct']}%",
            f"Battery Remaining  : {info['battery_remaining_mah']} mAh",
            f"Battery Usage      : {info['battery_usage_mah']} mAh",
            f"Battery Impedance  : {info['battery_impedance_mohm']} mOhm",
            f"LoRa Network ID    : {info['lorawan_network_id']}",
            f"LoRa Last RSSI     : {info['last_dl_rssi_dbm']} dBm",
            f"LoRa Last SNR      : {info['last_dl_snr_db']} dB",
            f"In Join Session    : {info['in_join_session']}",
            f"Ever Joined        : {info['ever_joined']}",
            f"Last Uplink Success: {info['last_uplink_success']}",
        ] + ([
            f"Last Uplink Retry  : {info['last_uplink_in_retry']}",
            f"Retry Count        : {info['last_uplink_retry_count']}",
        ] if has_retry else []) + ([
            f"Init Status        : 0x{info['init_status']:02X}"
            + (" (OK)" if info["init_status"] == 0
               else f" (GAGAL: {', '.join(info['init_failed_steps'])})"),
        ] if has_init else []) + ([
            f"Power Recovery Left: {info['recovery_remaining_min']:.2f} menit",
        ] if has_recovery else []))

        return f"OK:{summary}\n{detail}"

    # Bit 0..7 init_status — urutan sama dengan firmware (lihat DevGetInfo.py SWM)
    INIT_STEPS = ["modules", "user_cfg", "lora_cfg", "lora_keys",
                  "serial", "profiling", "boot_cfg", "persist"]

    @classmethod
    def _init_failed_steps(cls, status: int) -> list:
        return [n for i, n in enumerate(cls.INIT_STEPS) if status & (1 << i)]

    def get_info(self) -> dict:
        """Return dict info setelah execute() dipanggil."""
        return getattr(self, "_last_info", {})

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    assert DevGetInfo._init_failed_steps(0) == []
    assert DevGetInfo._init_failed_steps(0x09) == ["modules", "lora_keys"]
    assert DevGetInfo._init_failed_steps(0xFF) == DevGetInfo.INIT_STEPS

    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = DevGetInfo().execute()
    print(result)
    sm.disconnect_all()
