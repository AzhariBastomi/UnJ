"""
commands/tm81/factory_outgoing_reset.py — Factory-Outgoing Reset (CMD 109)

Reset operasional "factory-outgoing": menghapus history/config/key EEPROM dan
mengembalikan device ke kondisi belum-diprovisioning, TANPA harus kembali ke
line produksi. DevEui dan Serial Number TETAP dipertahankan (SN di page 58
tidak disentuh sama sekali oleh command ini).

Yang dihapus/direset:
  - EEPROM history (page 0-23), key LoRaWAN (54-55), config radio LoRa (57),
    user config (60), diff counter-sensor (61), progress OTA (62)
  - EUI page 63 ditulis ulang: DevEui TETAP (bound ke SN), JoinEui kembali ke
    default kompilasi
  - page 56 [0:4] (field energy milik App) DI-NOL-KAN — lihat catatan di bawah
  - Properti LoRaWAN (key, join eui, class, mode) kembali ke default per-device
  - Boot reason -> FIRST_BOOT, config sensor & user kembali ke default

Yang TIDAK disentuh:
  - page 56 [4:16] (record sesi Bootloader — lihat bl_get_session.py).
    PERHATIAN: page 56 dimiliki dua pihak. Bootloader memegang [4:16]
    (stamp/state/counter) dan itu selamat; [0:4] (energy, milik App) IKUT
    di-nol-kan oleh cmd 109. Jadi page 56 TIDAK utuh 16 byte setelah reset —
    verifikasi wipe harus menilai [4:16] saja (lihat eeprom_page_sweep.py).
    Referensi: SWM_Test_Scripts/docs/factory_outgoing_reset.feature:133-141,268
  - page 58 (Serial Number)
  - page 59 (boot cfg fw size/crc — validasi jump jump-gate tetap kuat)

TX: 4 byte magic ASCII "FACT" (hardcode di sini, bukan dari UI/params — lihat
guard confirm di bawah).
RX payload (5 byte):
  [0]  overall          0x11 = ACK (semua stage sukses), selain itu = NAK
  [1]  stage eeprom_wipe  0 = OK
  [2]  stage boot_reason  0 = OK
  [3]  stage lora_props   0 = OK
  [4]  stage defaults     0 = OK

Device soft-reset sendiri kalau semua stage sukses — sesi/koneksi IrDA akan
putus sesaat, ini normal, bukan error. Hanya berlaku di build APP.

DESTRUKTIF — hanya jalan kalau step diberi params {"confirm": true} di
_steps.json / row test (analog --yes pada versi CLI SWM).

Referensi: SWM_Test_Scripts/Src/FactoryOutgoingReset.py
           SWM_Test_Scripts/docs/factory_outgoing_reset.feature
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

FACTORY_RESET_MAGIC = b"FACT"
STAGE_NAMES = ("eeprom_wipe", "boot_reason", "lora_props", "defaults")


class FactoryOutgoingReset(TM81Command):

    RETRIES = 1   # destruktif + soft reset; jangan dikirim ulang

    TIMEOUT = 3.0

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._confirm = bool(p.get("confirm", False))

    def execute(self) -> str:
        if not self._confirm:
            return (
                "NG:destruktif — butuh params confirm=true untuk jalan "
                "(hapus history, key, config; DevEui & SN dipertahankan)"
            )

        result = self.xfer(CmdId.USR_FACTORY_RESET, FACTORY_RESET_MAGIC, timeout=self.TIMEOUT)
        if not result.valid:
            if result.error == "NAK":
                return "NG:NAK — magic ditolak, atau cmd 109 belum dikenal firmware"
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 5:
            return f"NG:payload terlalu pendek ({len(d)} byte, harusnya 5)"

        overall = d[0]
        stages = {name: d[1 + i] for i, name in enumerate(STAGE_NAMES)}
        all_ok = overall == 0x11 and all(v == 0 for v in stages.values())

        for name, status in stages.items():
            _log.debug(f"  {name}: {'OK' if status == 0 else f'ERROR({status})'}")

        detail = "\n".join(
            f"{name:<12}: {'OK' if status == 0 else f'ERROR ({status})'}"
            for name, status in stages.items()
        )

        if all_ok:
            return (
                "OK:factory-outgoing reset selesai — device soft-reset, "
                "DevEui/SN dipertahankan\n" + detail
            )
        return f"NG:reset tidak lengkap — satu atau lebih stage gagal\n{detail}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = FactoryOutgoingReset(params={"confirm": True}).execute()
    print(result)
    sm.disconnect_all()
