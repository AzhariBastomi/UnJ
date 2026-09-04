"""
commands/bexa/ftm_get_info.py — FTM Get Info commands.

  GetBluetoothInfo    (0x00) — Baca info Bluetooth dari device
  GetTactileInfo      (0x01) — Baca info Tactile Sensor
  GetHapticInfo       (0x02) — Baca info Haptic Motor
  GetCoulombInfo      (0x03) — Baca info Coulomb Counter
"""

try:
    from commands.bexa.base import BexaCommand, CmdFTM
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.bexa.base import BexaCommand, CmdFTM


class GetBluetoothInfo(BexaCommand):
    """FTM 0x00 — Get Bluetooth Info (via DEBUG UART di device)."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.GET_BT_INFO)
        if not r.valid:
            return f"NG:{r.error}"
        # Payload: [MAC(6B)][FW_VER(2B)][...] — format tergantung firmware
        if r.payload:
            return f"OK:BT Info {r.payload.hex(' ')}"
        return "OK:BT Info ACK diterima"


class GetTactileInfo(BexaCommand):
    """FTM 0x01 — Get Tactile Sensor Info (via DEBUG UART di device)."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.GET_TACTILE_INFO)
        if not r.valid:
            return f"NG:{r.error}"
        if r.payload:
            return f"OK:Tactile Info {r.payload.hex(' ')}"
        return "OK:Tactile Info ACK diterima"


class GetHapticInfo(BexaCommand):
    """FTM 0x02 — Get Haptic Info (via DEBUG UART di device)."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.GET_HAPTIC_INFO)
        if not r.valid:
            return f"NG:{r.error}"
        if r.payload:
            return f"OK:Haptic Info {r.payload.hex(' ')}"
        return "OK:Haptic Info ACK diterima"


class GetCoulombInfo(BexaCommand):
    """FTM 0x03 — Get Coulomb Counter Info (via DEBUG UART di device)."""

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.GET_COULOMB_INFO)
        if not r.valid:
            return f"NG:{r.error}"
        if r.payload:
            return f"OK:Coulomb Info {r.payload.hex(' ')}"
        return "OK:Coulomb Info ACK diterima"
