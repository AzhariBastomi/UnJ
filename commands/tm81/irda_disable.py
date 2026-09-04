"""commands/tm81/irda_disable.py — IrDA Disable (CMD 0x01)"""
import logging
_log = logging.getLogger(__name__)
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class IrdaDisable(TM81Command):
    def execute(self) -> str:
        result = self.xfer(CmdId.IRDA_DISABLE)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug("  IrDA Disable → OK")
        return "OK:IrDA dinonaktifkan"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = IrdaDisable().execute()
    print(result)
    sm.disconnect_all()
