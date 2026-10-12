"""
commands/tm81/dev_get_info.py — Get Device Info (CMD 0x1A)
Response payload — app v1.10.0 memperkecil battery impedance dari 2 byte
(mOhm) jadi 1 byte (Ohm), jadi payload 27 → 26 byte dan SEMUA field setelah
byte [4] bergeser 1 byte ke bawah. Layout dibedakan dari panjang payload:
len == 26 → layout baru (o = 5), selain itu → layout lama (o = 6).

  [0]        Sensor Intensity
  [1]        Sensor Indication
  [2-3]      Battery INTP (little-endian)
  [4]        Battery Impedance, Ohm   (layout lama: [4-5], mOhm)
  [o+0..1]   Battery Usage (mAh)
  [o+2..3]   Battery Capacity Remaining (mAh)
  [o+4]      Battery Percentage
  [o+5..8]   LoRaWAN Network ID (little-endian → big-endian hex)
  [o+9]      Last Downlink RSSI (signed)
  [o+10]     Last Downlink SNR (signed)
  [o+11]     Is in Join/Uplink Session
  [o+12]     Is Ever Joined
  [o+13]     Is Last Uplink Success
  [o+14]     Is Last Uplink in Retry      (payload >= o+16)
  [o+15]     Last Uplink Retry Count      (payload >= o+16)
  [o+16]     Init Status bitmask          (payload >= o+17)
  [o+17..20] Remaining Power Recovery Time, detik (payload >= o+21)

Firmware lama mengirim 20 byte — field di atasnya hanya dibaca kalau ada.
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

        new_layout, o = self._layout(d)
        if len(d) < o + 14:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        def signed(b):
            return b if b < 128 else b - 256

        info = {
            "sensor_intensity":         d[0],
            "sensor_indication":        d[1],
            "battery_intp":             d[2] | (d[3] << 8),
            "battery_impedance":        d[4] if new_layout else d[4] | (d[5] << 8),
            "battery_impedance_unit":   "Ohm" if new_layout else "mOhm",
            "battery_usage_mah":        d[o + 0] | (d[o + 1] << 8),
            "battery_remaining_mah":    d[o + 2] | (d[o + 3] << 8),
            "battery_pct":              d[o + 4],
            "lorawan_network_id":       int.from_bytes(d[o + 5:o + 9], "little").to_bytes(4, "big").hex(),
            "last_dl_rssi_dbm":         signed(d[o + 9]),
            "last_dl_snr_db":           signed(d[o + 10]),
            "in_join_session":          bool(d[o + 11]),
            "ever_joined":              bool(d[o + 12]),
            "last_uplink_success":      bool(d[o + 13]),
        }
        has_retry = len(d) >= o + 16
        if has_retry:
            info["last_uplink_in_retry"]    = bool(d[o + 14])
            info["last_uplink_retry_count"] = d[o + 15]
        has_init = len(d) >= o + 17
        if has_init:
            info["init_status"]        = d[o + 16]
            info["init_failed_steps"]  = self._init_failed_steps(d[o + 16])
        has_recovery = len(d) >= o + 21
        if has_recovery:
            info["recovery_remaining_min"] = int.from_bytes(d[o + 17:o + 21], "little") / 60

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
            f"Battery Impedance  : {info['battery_impedance']} {info['battery_impedance_unit']}",
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
        ] if has_recovery else []) + [
            f"Payload Len        : {len(d)} byte"
            + ("" if has_recovery else f"  <- < {o + 21}, field power recovery tidak dikirim device"),
        ])

        return f"OK:{summary}\n{detail}"

    @staticmethod
    def _layout(d) -> tuple:
        """(new_layout, o) — app v1.10.0 memperkecil batt_impedance 2 byte
        (mOhm) -> 1 byte (Ohm), payload 27 -> 26, jadi semua field setelah
        byte [4] bergeser 1 byte. Dibedakan dari panjang payload.
        Referensi: SWM Lib/Env.py TSM_SCP_RESP_LEN_DEV_INFO = 26."""
        new_layout = len(d) == 26
        return new_layout, 5 if new_layout else 6

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
    # layout baru (26B) vs lama (27B) — offset field setelah impedance
    assert DevGetInfo._layout(bytes(26)) == (True, 5)
    assert DevGetInfo._layout(bytes(27)) == (False, 6)
    assert DevGetInfo._layout(bytes(20)) == (False, 6)

    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = DevGetInfo().execute()
    print(result)
    sm.disconnect_all()
