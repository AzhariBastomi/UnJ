"""commands/tm81/lora_set_dev_addr.py — Set DevAddr (CMD 0x13)"""
import logging
_log = logging.getLogger(__name__)
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class LoraSetDevAddr(TM81Command):
    DEFAULT_DEV_ADDR = 0x0100000B

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        raw = p.get("dev_addr", self.DEFAULT_DEV_ADDR)
        # Terima int, "0xABCD1234", atau plain hex string
        if isinstance(raw, str):
            raw = raw.strip()
            self._dev_addr = int(raw, 16) if raw.lower().startswith("0x") else int(raw, 16)
        else:
            self._dev_addr = int(raw)

    def execute(self) -> str:
        if self._dev_addr == 0:
            return "NG:DevAddr tidak boleh 0x00000000. Cek Commissioning Settings."
        data = self._dev_addr.to_bytes(4, "little")
        result = self.xfer(CmdId.SET_DEV_ADDR, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug(f"  Set DevAddr=0x{self._dev_addr:08X} → OK")
        return f"OK:DevAddr=0x{self._dev_addr:08X}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    params = {"dev_addr": "01234567"}  # 8 hex chars
    result = LoraSetDevAddr(params=params).execute()
    print(result)
    sm.disconnect_all()
