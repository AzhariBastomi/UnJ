"""commands/tm81/lora_set_adr.py — Set LoRa ADR / Adaptive Data Rate (CMD 0x25)

adr: 0=OFF, 1=ON
Referensi: SWM_Test_Scripts/Src/LoraSetAdr.py (TSM_SCP_CMD_SET_LORA_ADR).
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


class LoraSetAdr(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._adr = 1 if int(p.get("adr", 1)) else 0  # default ADR ON, sama dgn SWM

    def execute(self) -> str:
        result = self.xfer(CmdId.SET_LORA_ADR, self._adr.to_bytes(1, "little"))
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        state = "ON" if self._adr else "OFF"
        _log.debug(f"  Set ADR={state} → OK")
        return f"OK:ADR {state}"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"adr": 1}  # 0=OFF, 1=ON
    result = LoraSetAdr(params=params).execute()
    print(result)
    sm.disconnect_all()
