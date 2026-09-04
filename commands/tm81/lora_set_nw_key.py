"""commands/tm81/lora_set_nw_key.py — Set NwKey (CMD 0x12)"""
import logging
_log = logging.getLogger(__name__)
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class LoraSetNwKey(TM81Command):
    DEFAULT_NW_KEY = bytes.fromhex("8833E75406D203F48F1F6D2CCC2815D8")  # 16 bytes

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        raw = p.get("nw_key", self.DEFAULT_NW_KEY.hex())
        raw = str(raw).strip().replace(":", "").replace(" ", "")
        try:
            self._nw_key = bytes.fromhex(raw) if raw else b""
        except ValueError:
            self._nw_key = b""

    def execute(self) -> str:
        if len(self._nw_key) != 16:
            return f"NG:NwKey harus 16 bytes (32 hex) - sekarang {len(self._nw_key)} bytes. Cek Commissioning Settings."
        result = self.xfer(CmdId.SET_NW_KEY, self._nw_key)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug(f"  Set NwKey={self._nw_key.hex(':')} → OK")
        return f"OK:NwKey={self._nw_key.hex(':').upper()}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"nw_key": "2B7E151628AED2A6ABF7158809CF4F3C"}  # 32 hex chars
    result = LoraSetNwKey(params=params).execute()
    print(result)
    sm.disconnect_all()
