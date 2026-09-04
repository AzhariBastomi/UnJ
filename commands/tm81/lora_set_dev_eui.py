"""commands/tm81/lora_set_dev_eui.py — Set DevEUI (CMD 0x0F)

Default DevEUI dapat di-override lewat params di tm81_test.json:
    "params": {"dev_eui": "0080E1010101010A"}
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


class LoraSetDevEui(TM81Command):
    DEFAULT_DEV_EUI = bytes.fromhex("0080E10101010104")  # 8 bytes

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        raw = p.get("dev_eui", self.DEFAULT_DEV_EUI.hex())
        raw = str(raw).strip().replace(":", "").replace(" ", "")
        try:
            self._dev_eui = bytes.fromhex(raw) if raw else b""
        except ValueError:
            self._dev_eui = b""

    def execute(self) -> str:
        if len(self._dev_eui) != 8:
            return f"NG:DevEUI harus 8 bytes (16 hex) - sekarang {len(self._dev_eui)} bytes. Cek Commissioning Settings."
        result = self.xfer(CmdId.SET_DEV_EUI, self._dev_eui)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug(f"  Set DevEUI={self._dev_eui.hex(':')} → OK")
        return f"OK:DevEUI={self._dev_eui.hex(':').upper()}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"dev_eui": "0080E1010101010A"}  # 16 hex chars
    result = LoraSetDevEui(params=params).execute()
    print(result)
    sm.disconnect_all()
