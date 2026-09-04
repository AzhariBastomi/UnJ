"""commands/tm81/lora_set_join_mode.py — Set LoRa Join Mode (CMD 0x14)

join_mode: 0=None, 1=ABP, 2=OTAA
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


class LoraSetJoinMode(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._mode = p.get("join_mode", 2)  # default OTAA

    def execute(self) -> str:
        data = self._mode.to_bytes(1, "little")
        result = self.xfer(CmdId.SET_JOIN_MODE, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        names = {0: "None", 1: "ABP", 2: "OTAA"}
        _log.debug(f"  Set JoinMode={names.get(self._mode, self._mode)} → OK")
        return f"OK:JoinMode={names.get(self._mode, self._mode)}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"join_mode": 0}  # 0=ABP, 1=OTAA
    result = LoraSetJoinMode(params=params).execute()
    print(result)
    sm.disconnect_all()
