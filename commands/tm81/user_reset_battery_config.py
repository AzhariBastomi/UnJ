"""
commands/tm81/user_reset_battery_config.py — Reset Battery/Coulomb-Counter
Config to Default (CMD 0x24)

Terpisah dari user_reset_config.py (CMD 0x09, reset user config umum) —
command ini khusus mereset config baterai/coulomb-counter ke default.

Referensi: SWM_Test_Scripts/Src/UserResetBatteryConfig.py
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


class UserResetBatteryConfig(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.RESET_BATTERY_CONFIG)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  User Reset Battery Config → OK")
        return "OK:config baterai direset ke default"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserResetBatteryConfig().execute()
    print(result)
    sm.disconnect_all()
