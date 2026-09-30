"""commands/tm81/standby_mode.py — Enter Standby Mode (CMD 0x0E)"""
import logging
_log = logging.getLogger(__name__)
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class StandbyMode(TM81Command):

    RETRIES = 1   # device masuk standby; jangan dikirim ulang
    def execute(self) -> str:
        result = self.xfer(CmdId.ENTER_STANDBY)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug("  Standby Mode → OK")
        return "OK:device masuk standby"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = StandbyMode().execute()
    print(result)
    sm.disconnect_all()
