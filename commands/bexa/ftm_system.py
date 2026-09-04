"""
commands/bexa/ftm_system.py — FTM System commands.

  BluetoothBurst  (0x04) — Connectionless FCC test (BT akan disconnect)
  WatchdogReset   (0x0D) — Reset watchdog
  BluetoothRfSig  (0x0E) — BT RF signal test
  Stop            (0x11) — Hentikan semua test case
"""

try:
    from commands.bexa.base import BexaCommand, CmdFTM
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.bexa.base import BexaCommand, CmdFTM


class BluetoothBurst(BexaCommand):
    """
    FTM 0x04 — Connectionless FCC Bluetooth Burst test.
    PERHATIAN: Bluetooth akan disconnect setelah perintah ini.
    Verifikasi menggunakan spectrum analyzer.
    """

    TIMEOUT = 3.0   # Tidak perlu tunggu lama — device disconnect setelahnya

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.BLUETOOTH_BURST, timeout=self.TIMEOUT)
        # Device mungkin disconnect sebelum ACK terkirim
        if not r.valid and "Timeout" in r.error:
            return "OK:BT Burst dimulai (device disconnect — verifikasi spectrum analyzer)"
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:BT Burst ACK diterima — verifikasi spectrum analyzer"


class WatchdogReset(BexaCommand):
    """FTM 0x0D — Reset watchdog timer."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.WATCHDOG_RESET)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:Watchdog reset"


class BluetoothRfSig(BexaCommand):
    """FTM 0x0E — Bluetooth RF Signal test."""

    TIMEOUT = 10.0

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.BT_RF_SIG, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        if r.payload:
            return f"OK:BT RF Sig {r.payload.hex(' ')}"
        return "OK:BT RF Signal test selesai"


class Stop(BexaCommand):
    """FTM 0x11 — Hentikan semua test case yang sedang berjalan."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.STOP)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:Stop — semua test dihentikan"
