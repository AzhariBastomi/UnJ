"""
commands/tm81/uptime_get.py — Get Bootloader Uptime (CMD 108 / 0x6C)

Membaca berapa lama device berdiam di mode Bootloader (residency) beserta
estimasi konsumsi energinya. Bootloader tidak tidur seperti App (arus rata-rata
~1000 uA), jadi waktu yang dihabiskan di BL — terutama saat OTA atau saat device
nyangkut karena image App tidak valid — harus ikut dihitung di model baterai.

Command yang sama dijawab oleh DUA build dengan arti berbeda:

  Di BOOTLOADER : counter LPTIM3 sedang berjalan.
                  live_session_ms > 0 (sesi yang sedang berlangsung),
                  cum_ms = yang sudah di-commit + live.
                  EEPROM kosong tetap ACK (last = 0, est = 0).

  Di APP        : tidak ada counter berjalan — nilai dibaca dari EEPROM page 55
                  yang di-commit bootloader sebelum lompat.
                  live_session_ms SELALU 0, last_session_ms = sesi BL terakhir.
                  Kalau belum ada record valid, device menjawab NAK.

RX payload (20 byte, little-endian):
  [0..7]   u64  cum_ms              total residency BL seumur hidup device
  [8..11]  u32  last_session_ms     durasi sesi BL terakhir yang di-commit
  [12..15] u32  live_session_ms     sesi yang sedang berjalan (0 di build App)
  [16..19] u32  est_consumption_uah floor(last_session_ms * 1000 uA / 3_600_000)

Referensi: SWM_Test_Scripts/Src/UptimeGet.py
           SWM_Test_Scripts/docs/bl_uptime.feature
           SWM_Test_Scripts/docs/bl_uptime_app.feature
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

# Arus rata-rata bootloader yang dipakai firmware untuk est_consumption_uah.
# Konstanta build BL_UPTIME_AVG_CURRENT_UA — ubah kalau firmware di-build lain.
BL_AVG_CURRENT_UA = 1000

_PAYLOAD_LEN = 20


class UptimeGet(TM81Command):
    """Baca uptime bootloader (cmd 108). Read-only, tidak mengubah state device."""

    TIMEOUT = 3.0

    @staticmethod
    def fmt_duration(ms: int) -> str:
        """Format milidetik jadi '1h 2m 3s 456ms'."""
        s, ms_rem = divmod(int(ms), 1000)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}h {m}m {s}s {ms_rem}ms"

    def execute(self) -> str:
        result = self.xfer(CmdId.BL_GET_UPTIME, timeout=self.TIMEOUT)

        if not result.valid:
            if result.error == "NAK":
                return (
                    "NG:NAK — belum ada record uptime di EEPROM (page 55). "
                    "Normal untuk device yang belum pernah commit sesi bootloader; "
                    "jalankan satu siklus App→BL→App dulu."
                )
            return f"NG:{result.error}"

        # Device membalas ACK polos = firmware belum mengenal cmd 108
        if result.error == "ACK" or not result.payload:
            return (
                "NG:device membalas ACK tanpa payload — firmware belum mendukung "
                "BL_GET_UPTIME (cmd 108). Butuh App/BL versi yang sudah punya fitur ini."
            )

        d = result.payload
        if len(d) < _PAYLOAD_LEN:
            return f"NG:payload terlalu pendek ({len(d)} byte, harusnya {_PAYLOAD_LEN})"

        cum_ms          = int.from_bytes(d[0:8],   "little")
        last_session_ms = int.from_bytes(d[8:12],  "little")
        live_session_ms = int.from_bytes(d[12:16], "little")
        est_uah         = int.from_bytes(d[16:20], "little")

        # live > 0 hanya mungkin kalau yang menjawab adalah build bootloader
        mode = "Bootloader" if live_session_ms > 0 else "App"

        info = {
            "mode":                mode,
            "cum_ms":              cum_ms,
            "last_session_ms":     last_session_ms,
            "live_session_ms":     live_session_ms,
            "est_consumption_uah": est_uah,
        }
        self._last_info = info
        for k, v in info.items():
            _log.debug(f"  {k}: {v}")

        # Sanity check ringan — bantu deteksi payload/endianness yang meleset
        if cum_ms < last_session_ms:
            _log.warning(
                "  [uptime] cum_ms (%d) < last_session_ms (%d) — nilai tidak konsisten",
                cum_ms, last_session_ms,
            )

        expected_uah = (last_session_ms * BL_AVG_CURRENT_UA) // 3_600_000
        if est_uah != expected_uah:
            _log.warning(
                "  [uptime] est_consumption_uah=%d, dihitung host=%d "
                "(BL_UPTIME_AVG_CURRENT_UA mungkin bukan %d uA)",
                est_uah, expected_uah, BL_AVG_CURRENT_UA,
            )

        # Baris pertama = summary singkat (tampil di row UI)
        brief = (
            f"[{mode}] cum: {self.fmt_duration(cum_ms)} | "
            f"last: {self.fmt_duration(last_session_ms)} | "
            f"{est_uah / 1000:.3f} mAh"
        )

        detail = "\n".join([
            f"Dijawab oleh        : build {mode}",
            f"Cumulative BL time  : {cum_ms} ms ({self.fmt_duration(cum_ms)})",
            f"Last BL session     : {last_session_ms} ms ({self.fmt_duration(last_session_ms)})",
            f"Live BL session     : {live_session_ms} ms ({self.fmt_duration(live_session_ms)})",
            f"Est. consumption    : {est_uah} uAh ({est_uah / 1000:.3f} mAh)",
            f"  (asumsi arus BL   : {BL_AVG_CURRENT_UA} uA)",
        ])

        return f"OK:{brief}\n{detail}"

    def get_info(self) -> dict:
        """Return dict hasil setelah execute() dipanggil."""
        return getattr(self, "_last_info", {})


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UptimeGet().execute()
    print(result)
    sm.disconnect_all()
