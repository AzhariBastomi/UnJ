"""commands/tm81/lora_set_dev_class.py — Set LoRa Device Class (CMD 0x15)

dev_class: 0=A, 1=B, 2=C
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


class LoraSetDevClass(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._cls = p.get("dev_class", 0)  # default Class A

    def execute(self) -> str:
        data = self._cls.to_bytes(1, "little")
        result = self.xfer(CmdId.SET_DEV_CLASS, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        names = {0: "A", 1: "B", 2: "C"}
        _log.debug(f"  Set DevClass={names.get(self._cls, self._cls)} → OK")
        return f"OK:Class {names.get(self._cls, self._cls)}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"dev_class": 0}  # 0=Class A, 2=Class C
    result = LoraSetDevClass(params=params).execute()
    print(result)
    sm.disconnect_all()
