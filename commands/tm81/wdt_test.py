"""
commands/tm81/wdt_test.py — Test Watchdog Timer (CMD 0x0D)
Device akan reset via WDT setelah command ini → koneksi putus adalah hasil normal.
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


class WdtTest(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_TEST_WDT, timeout=5.0)
        # Device reset setelah WDT, ACK atau timeout dua-duanya normal
        if result.error in ("ACK", "Timeout"):
            _log.debug("  WDT Test → device akan reset (normal)")
            return "OK:WDT triggered — device akan reset"
        if not result.valid:
            return f"NG:{result.error}"
        return "OK:WDT triggered — device akan reset"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = WdtTest().execute()
    print(result)
    sm.disconnect_all()
