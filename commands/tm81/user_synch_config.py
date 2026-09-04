"""
commands/tm81/user_synch_config.py — Sync User Config (CMD 0x06)
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


class UserSynchConfig(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_SYNC_CFG)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  User Sync Config → OK")
        return "OK:config disinkronisasi"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserSynchConfig().execute()
    print(result)
    sm.disconnect_all()
