"""
commands/tm81/eeprom_page_sweep.py — EEPROM Page Sweep/Read (CMD 110)

Baca isi page EEPROM ZD24C08A (64 page x 16 byte) via IrDA. Dipakai untuk
verifikasi manual isi EEPROM, dan khususnya untuk memvalidasi hasil
factory_outgoing_reset.py (params expect_wipe=true): page yang seharusnya
di-wipe (0x00) vs page yang harus tetap terisi setelah reset.

TX: 1 byte page id (0..63)
RX payload: 16 byte isi page mentah. NAK/timeout = page id di luar jangkauan
atau bus I2C internal device gagal (dilaporkan READ-FAIL).

Params:
  page         int   baca satu page saja (0..63). Default: sweep semua 64 page.
  expect_wipe  bool  judge tiap page terhadap state pasca factory-outgoing
                      reset (SCP 109) — page WIPE_EXPECT_ZERO harus 0x00,
                      page PRESERVED harus TIDAK all-zero. Khusus page 56,
                      yang dinilai hanya record sesi [4:16]; [0:4] (energy
                      milik App) memang di-nol-kan oleh cmd 109 dan
                      ditampilkan apa adanya. Jalankan SETELAH
                      factory_outgoing_reset + device selesai soft-reset,
                      selagi ada di image App (command hanya terdaftar di
                      build App).

Referensi: SWM_Test_Scripts/Src/EepromPageSweep.py
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

EEPROM_TOTAL_PAGES = 64
PAGE_SIZE = 16

# Page yang di-wipe (0x00) oleh SCP 109 dan TIDAK ditulis ulang sesudahnya.
WIPE_EXPECT_ZERO_PAGES = set(list(range(0, 24)) + [54, 55, 57, 61, 62])
# Page yang ditulis ulang oleh reset itu sendiri (non-zero sesudahnya).
REWRITTEN_PAGES = {60, 63}
# Page yang harus tetap utuh (tidak disentuh sama sekali).
PRESERVED_PAGES = {56, 58, 59}

# Page 56 dimiliki dua pihak: [0:4] = energy milik App (DI-NOL-KAN oleh SCP 109),
# [4:16] = record sesi Bootloader (harus selamat). Verifikasi wipe hanya boleh
# menilai [4:16]; menilai seluruh 16 byte bisa lolos/gagal palsu.
# Referensi: SWM_Test_Scripts/docs/factory_outgoing_reset.feature:133-141,268
PAGE56_RECORD_OFFSET = 4


def _fmt(data: bytes) -> str:
    return " ".join(f"{b:02x}" for b in data)


class EepromPageSweep(TM81Command):

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._page = p.get("page")
        self._expect_wipe = bool(p.get("expect_wipe", False))

    def read_page(self, page_id: int):
        result = self.xfer(CmdId.EEPROM_PAGE_READ, bytes([page_id]))
        if not result.valid or len(result.payload) < PAGE_SIZE:
            return None
        return result.payload[:PAGE_SIZE]

    def execute(self) -> str:
        if self._page is not None:
            return self._dump_page(int(self._page))
        return self._sweep(0, EEPROM_TOTAL_PAGES - 1, self._expect_wipe)

    def _dump_page(self, page_id: int) -> str:
        if not (0 <= page_id <= EEPROM_TOTAL_PAGES - 1):
            return f"NG:page id harus di [0, {EEPROM_TOTAL_PAGES - 1}]"
        data = self.read_page(page_id)
        if data is None:
            return f"NG:page {page_id} READ-FAIL (NAK/timeout)"
        return f"OK:page {page_id}: {_fmt(data)}"

    def _sweep(self, start: int, end: int, expect_wipe: bool) -> str:
        lines = []
        wipe_failed = False

        for page_id in range(start, end + 1):
            data = self.read_page(page_id)
            if data is None:
                lines.append(f"page {page_id:3d}: READ-FAIL (NAK/timeout)")
                if expect_wipe and page_id in (WIPE_EXPECT_ZERO_PAGES | PRESERVED_PAGES):
                    wipe_failed = True
                continue

            verdict = ""
            if expect_wipe:
                if page_id in WIPE_EXPECT_ZERO_PAGES:
                    ok = all(b == 0 for b in data)
                    verdict = "zero-expect [OK]" if ok else "zero-expect [FAIL]"
                    wipe_failed = wipe_failed or not ok
                elif page_id in REWRITTEN_PAGES:
                    verdict = "rewritten (info)"
                elif page_id == 56:
                    # Judge HANYA record sesi [4:16] — [0:4] (energy) memang
                    # di-nol-kan oleh cmd 109, bukan tanda wipe gagal.
                    record = data[PAGE56_RECORD_OFFSET:]
                    ok = any(b != 0 for b in record)
                    energy = int.from_bytes(data[:PAGE56_RECORD_OFFSET], "little")
                    verdict = (f"preserved record [{'kept' if ok else 'LOST!'}] "
                               f"energy={energy}")
                    wipe_failed = wipe_failed or not ok
                elif page_id in PRESERVED_PAGES:
                    ok = any(b != 0 for b in data)
                    verdict = "preserved [kept]" if ok else "preserved [LOST!]"
                    wipe_failed = wipe_failed or not ok

            lines.append(f"page {page_id:3d}: {_fmt(data)}  {verdict}".rstrip())

        detail = "\n".join(lines)
        _log.debug("  EEPROM sweep %d..%d done (expect_wipe=%s)", start, end, expect_wipe)

        if expect_wipe:
            if wipe_failed:
                return f"NG:EEPROM wipe state tidak sesuai factory-outgoing reset\n{detail}"
            return f"OK:EEPROM wipe state sesuai factory-outgoing reset\n{detail}"

        return f"OK:sweep {start}..{end} selesai\n{detail}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = EepromPageSweep(params={"expect_wipe": True}).execute()
    print(result)
    sm.disconnect_all()
