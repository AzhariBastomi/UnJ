"""
commands/tm81/sensor_do_reset_config.py — Sensor Reset Config (CMD 0x03)
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


class SensorDoResetConfig(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.SENSOR_RESET_CONFIG)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        _log.debug("  Sensor Reset Config → OK")
        return "OK"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = SensorDoResetConfig().execute()
    print(result)
    sm.disconnect_all()
