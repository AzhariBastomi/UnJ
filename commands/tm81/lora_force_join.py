"""
commands/tm81/lora_force_join.py — Force LoRaWAN Join (CMD 0x26 / 38)

Hanya jalan kalau device dalam keadaan ACTIVATED. Balasan: payload 2 byte
[0] scp status, [1] activation status (1 = join dipicu, 0 = device deactivate).
Firmware lama yang belum punya handler ini balas NAK.

Referensi: SWM_Test_Scripts/Src/LoraForceJoin.py (TSM_SCP_CMD_FORCE_JOIN_LORA).
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


class LoraForceJoin(TM81Command):
    # Join tidak boleh dipicu dua kali kalau balasan telat sampai.
    RETRIES = 1

    def execute(self) -> str:
        result = self.xfer(CmdId.FORCE_JOIN_LORA)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 2:
            # Firmware balas ACK saja (tanpa status) — join dianggap terkirim.
            _log.debug("  Force join: ACK tanpa status activation")
            return "OK:Join dipicu (device tidak kirim status activation)"

        if d[1] == 1:
            _log.debug("  Force join: activation=1 → join dipicu")
            return "OK:Join dipicu"
        _log.debug("  Force join: activation=0 → device deactivate")
        return "NG:Device deactivate — join tidak dipicu"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = LoraForceJoin().execute()
    print(result)
    sm.disconnect_all()
