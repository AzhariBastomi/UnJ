"""
commands/tm81/bl_get_session.py — Get Bootloader Session Record (CMD 108 / 0x6C)

Membaca record sesi bootloader: berapa lama device berdiam di mode Bootloader
pada rantai sesi terakhir, dan sudah berapa kali device masuk Bootloader.
Bootloader tidak tidur seperti App (arus rata-rata ~1000 uA), jadi waktu yang
dihabiskan di BL — terutama saat OTA atau saat device nyangkut karena image App
tidak valid — harus ikut dihitung di model baterai. Sisi App yang mengalikan
durasi ini dengan konstanta cold-boot (Profiling_ApplyBlSession); firmware
TIDAK mengirim estimasi energi lewat command ini.

Record tersimpan di EEPROM page 56 (NVS_PAGE_LORA_PROFILING_CFG). Page ini
dibagi dua pemilik: Bootloader hanya menulis byte [4:16] (stamp/state/counter),
App hanya menulis byte [0:4] (energy) lewat read-modify-write.

Command yang sama dijawab oleh DUA build:

  Di BOOTLOADER : record dibaca dari EEPROM — ISI SESI SEBELUMNYA, bukan sesi
                  yang sedang berjalan. Tidak ada counter live; record baru
                  ditulis saat close (sebelum jump / soft reset 102/103).

  Di APP        : record yang sama, ditulis bootloader tepat sebelum lompat.

Beda dengan versi lama (BL_GET_UPTIME, payload 20 byte, EEPROM page 55): versi
itu memakai counter LPTIM3 + akumulator cum_ms seumur hidup dan bisa dibaca
live. Versi session memakai stamp RTC per-sesi, tidak punya total kumulatif,
tapi bisa merangkai durasi lintas soft-reset (102/103) dan menghitung berapa
kali device masuk BL.

RX payload (17 byte, little-endian):
  [0]      u8   valid               1 = state byte berisi record sesi yang sah
  [1..4]   u32  energy              budget energi kumulatif MILIK APP —
                                    diteruskan apa adanya, bukan hasil sesi
  [5..8]   u32  start_time_ms       stamp mulai, sudah dikurangi durasi rantai
                                    yang dibawa (wrap u32: start = 0 - carried)
  [9..12]  u32  finish_time_ms      stamp selesai, relatif boot Bootloader
  [13]     u8   state               1 = PENDING_APP (rantai masih terbuka,
                                    ditutup oleh soft reset 102/103)
                                    2 = ENTERED_APP (rantai dikonsumsi jump)
  [14..16] u24  session_counter     naik tiap boot BL, saturasi di 0xFFFFFF

durasi rantai = (finish_time_ms - start_time_ms) & 0xFFFFFFFF

Catatan akurasi: stamp bersumber dari RTC (LSI), yang berjalan ~2.4% lebih
lambat terhadap predivider 127/255 — durasi mewarisi bias itu.

Referensi: SWM_Test_Scripts/Src/BlGetSession.py
           SWM_Test_Scripts/docs/bl_session.feature
           Libraries/Custom/Inc/calestek_bl_session.h
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

# Arus rata-rata bootloader — hanya untuk estimasi tampilan di sisi host.
# Firmware TIDAK mengirim nilai ini pada cmd 108 (beda dengan BL_GET_UPTIME lama).
BL_AVG_CURRENT_UA = 1000

_PAYLOAD_LEN       = 17   # common block minimum (firmware lama, tanpa image byte)
_APP_PAYLOAD_LEN   = 18   # + [17] u8 image (app >= v1.4.0)
_BL_PAYLOAD_LEN    = 21   # + [18:21] u24 live_session_counter (BL >= v1.3.0)
_LEGACY_UPTIME_LEN = 20   # payload BL_GET_UPTIME lama — cek EXACT, krn payload BL baru (image+live_counter) = 21B, juga >=20

IMAGE_NAMES = {1: "APP", 2: "BOOTLOADER"}

# calestek_bl_session_state_t — nilainya sengaja sama dengan state_handle_t
STATE_NAMES = {
    0: "NONE",
    1: "PENDING_APP",   # PROFILING_STATE_START_E  — rantai sesi masih terbuka
    2: "ENTERED_APP",   # PROFILING_STATE_FINISH_E — rantai dikonsumsi jump ke App
}


class BLGetSession(TM81Command):
    """Baca record sesi bootloader (cmd 108). Read-only, tidak mengubah state device."""

    TIMEOUT = 3.0

    @staticmethod
    def fmt_duration(ms: int) -> str:
        """Format milidetik jadi '1h 2m 3s 456ms'."""
        s, ms_rem = divmod(int(ms), 1000)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}h {m}m {s}s {ms_rem}ms"

    def execute(self) -> str:
        result = self.xfer(CmdId.BL_GET_SESSION, timeout=self.TIMEOUT)

        if not result.valid:
            if result.error == "NAK":
                return (
                    "NG:NAK — firmware tidak mengenal cmd 108. Build BL_GET_SESSION "
                    "selalu membalas ACK (valid=0 kalau belum ada record), jadi NAK "
                    "berarti App/BL di device belum punya fitur ini."
                )
            return f"NG:{result.error}"

        # Device membalas ACK polos = firmware belum mengenal cmd 108
        if result.error == "ACK" or not result.payload:
            return (
                "NG:device membalas ACK tanpa payload — firmware belum mendukung "
                "BL_GET_SESSION (cmd 108). Butuh App/BL versi yang sudah punya fitur ini."
            )

        d = result.payload

        # Deteksi firmware generasi lama (BL_GET_UPTIME, payload PERSIS 20 byte).
        # Bukan >=20: payload BL_GET_SESSION dari bootloader baru (image+live_counter)
        # sudah 21 byte, jadi >=20 juga — harus exact match biar tidak salah deteksi.
        if len(d) == _LEGACY_UPTIME_LEN:
            return (
                f"NG:payload {len(d)} byte — device menjalankan firmware lama "
                f"BL_GET_UPTIME (LPTIM3, EEPROM page 55), bukan BL_GET_SESSION "
                f"({_PAYLOAD_LEN} byte, page 56). Flash build session-counter dulu."
            )

        if len(d) < _PAYLOAD_LEN:
            return f"NG:payload terlalu pendek ({len(d)} byte, harusnya >= {_PAYLOAD_LEN})"

        # Per-responder extension (app >= v1.4.0 / BL >= v1.3.0): [17] u8 image,
        # dan khusus bootloader [18:21] u24 live_session_counter.
        image_name = None
        live_counter = None
        if len(d) >= _APP_PAYLOAD_LEN:
            image = d[_PAYLOAD_LEN]
            image_name = IMAGE_NAMES.get(image, f"UNKNOWN({image})")
            if image == 2 and len(d) >= _BL_PAYLOAD_LEN:
                live_counter = int.from_bytes(d[18:21], "little")

        valid          = d[0]
        energy         = int.from_bytes(d[1:5],   "little")
        start_ms       = int.from_bytes(d[5:9],   "little")
        finish_ms      = int.from_bytes(d[9:13],  "little")
        state          = d[13]
        session_count  = int.from_bytes(d[14:17], "little")

        if not valid:
            return (
                "NG:valid=0 — belum ada record sesi di EEPROM page 56 (page pabrik "
                "terbaca 0xFF, atau belum pernah ada sesi BL yang ditutup). Normal "
                "untuk device baru; jalankan satu siklus App→BL→App dulu."
            )

        state_name = STATE_NAMES.get(state, f"UNKNOWN({state})")

        # Subtraksi u32 polos — sama seperti CalculateProfiling di firmware.
        # start_time sengaja di-wrap (0 - carried) supaya hasilnya = total rantai.
        duration_ms = (finish_ms - start_ms) & 0xFFFFFFFF

        # Estimasi host-side; firmware tidak mengirimkan angka ini pada cmd 108.
        est_uah = (duration_ms * BL_AVG_CURRENT_UA) // 3_600_000

        info = {
            "valid":            valid,
            "session_counter":  session_count,
            "state":            state,
            "state_name":       state_name,
            "start_time_ms":    start_ms,
            "finish_time_ms":   finish_ms,
            "duration_ms":      duration_ms,
            "energy":           energy,
            "est_consumption_uah": est_uah,
            "image_name":       image_name,
            "live_counter":     live_counter,
        }
        self._last_info = info
        for k, v in info.items():
            _log.debug(f"  {k}: {v}")

        # Sanity check ringan — bantu deteksi payload/endianness yang meleset
        if state not in STATE_NAMES or state == 0:
            _log.warning("  [bl_session] state byte tidak dikenal: %d", state)
        if session_count == 0xFFFFFF:
            _log.warning("  [bl_session] session_counter saturasi di 0xFFFFFF")
        if duration_ms > 24 * 60 * 60 * 1000:
            _log.warning(
                "  [bl_session] durasi %d ms (>24 jam) — cek rantai sesi / stamp RTC",
                duration_ms,
            )

        # Baris pertama = summary singkat (tampil di row UI)
        brief = (
            f"#{session_count} [{state_name}] "
            f"durasi: {self.fmt_duration(duration_ms)} | "
            f"~{est_uah / 1000:.3f} mAh"
        )

        detail_lines = [
            f"Session counter     : {session_count}",
            f"State               : {state_name} ({state})",
            f"Durasi rantai BL    : {duration_ms} ms ({self.fmt_duration(duration_ms)})",
            f"Start time          : {start_ms} ms (u32, sudah di-wrap oleh carried chain)",
            f"Finish time         : {finish_ms} ms (relatif boot Bootloader)",
            f"Energy (milik App)  : {energy} (field page apa adanya, bukan hasil sesi)",
            f"Est. consumption    : {est_uah} uAh ({est_uah / 1000:.3f} mAh) — hitungan host",
            f"  (asumsi arus BL   : {BL_AVG_CURRENT_UA} uA)",
        ]
        if image_name is not None:
            detail_lines.insert(0, f"Responder           : {image_name}")
        if live_counter is not None:
            detail_lines.append(
                f"Live session counter: {live_counter} (sesi BL berjalan, persisted saat close)"
            )
        detail = "\n".join(detail_lines)

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
    result = BLGetSession().execute()
    print(result)
    sm.disconnect_all()
