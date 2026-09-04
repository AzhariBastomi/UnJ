"""commands/tm81/lora_set_app_key.py — Set AppKey (CMD 0x11)"""
import logging
_log = logging.getLogger(__name__)
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class LoraSetAppKey(TM81Command):
    DEFAULT_APP_KEY = bytes.fromhex("8833E75406D203F48D1F6D2CCC2815D8")  # 16 bytes

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        raw = p.get("app_key", self.DEFAULT_APP_KEY.hex())
        raw = str(raw).strip().replace(":", "").replace(" ", "")
        try:
            self._app_key = bytes.fromhex(raw) if raw else b""
        except ValueError:
            self._app_key = b""

    def execute(self) -> str:
        if len(self._app_key) != 16:
            return f"NG:AppKey harus 16 bytes (32 hex) - sekarang {len(self._app_key)} bytes. Cek Commissioning Settings."
        result = self.xfer(CmdId.SET_APP_KEY, self._app_key)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug(f"  Set AppKey={self._app_key.hex(':')} → OK")
        return f"OK:AppKey={self._app_key.hex(':').upper()}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"app_key": "2B7E151628AED2A6ABF7158809CF4F3C"}  # 32 hex chars
    result = LoraSetAppKey(params=params).execute()
    print(result)
    sm.disconnect_all()
