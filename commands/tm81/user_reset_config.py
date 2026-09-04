"""
commands/tm81/user_reset_config.py — Reset User Config to Default (CMD 0x09)
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


class UserResetConfig(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_RESET_CONFIG)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  User Reset Config → OK")
        return "OK:config direset ke default"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserResetConfig().execute()
    print(result)
    sm.disconnect_all()
