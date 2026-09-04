"""
commands/bexa/ftm_actuator.py — FTM Actuator commands.

  HapticVibrating   (0x06) — Haptic motor bergetar bergantian L/R
  LedActionRgb      (0x08) — LED Action berkedip Merah, Hijau, Biru
  LedPowerRgb       (0x09) — LED Power berkedip Merah, Hijau, Biru
  LightbarPulsing   (0x0A) — Lightbar pulsing 0-8 kiri dan kanan
  BuzzerPlaying     (0x0B) — Buzzer berbunyi
"""

try:
    from commands.bexa.base import BexaCommand, CmdFTM
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.bexa.base import BexaCommand, CmdFTM


class HapticVibrating(BexaCommand):
    """
    FTM 0x06 — Haptic motor bergetar bergantian kiri dan kanan.
    Operator memverifikasi getaran terasa di kedua sisi.
    """

    TIMEOUT = 10.0  # Motor bergetar beberapa siklus

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.HAPTIC_VIBRATING, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:Haptic motor bergetar (verifikasi manual: kiri + kanan)"


class LedActionRgb(BexaCommand):
    """
    FTM 0x08 — LED Action berkedip Merah, Hijau, Biru secara bergantian.
    Operator memverifikasi ketiga warna terlihat.
    """

    TIMEOUT = 10.0

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.LED_ACTION_RGB, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:LED Action flash RGB (verifikasi manual: merah, hijau, biru)"


class LedPowerRgb(BexaCommand):
    """
    FTM 0x09 — LED Power berkedip Merah, Hijau, Biru secara bergantian.
    """

    TIMEOUT = 10.0

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.LED_POWER_RGB, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:LED Power flash RGB (verifikasi manual: merah, hijau, biru)"


class LightbarPulsing(BexaCommand):
    """
    FTM 0x0A — Lightbar pulsing dari 0 ke 8, kiri dan kanan.
    """

    TIMEOUT = 15.0

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.LIGHTBAR_PULSING, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:Lightbar pulsing selesai (verifikasi manual: semua LED berurutan)"


class BuzzerPlaying(BexaCommand):
    """
    FTM 0x0B — Buzzer berbunyi.
    """

    TIMEOUT = 10.0

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.BUZZER_PLAYING, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        return "OK:Buzzer playing selesai"
