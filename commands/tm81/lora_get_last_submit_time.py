"""
commands/tm81/lora_get_last_submit_time.py — Get Last LoRa Submit Time (CMD 0x23)
Response payload (4 bytes): unix timestamp (little-endian).
"""

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

import datetime
import logging
_log = logging.getLogger(__name__)


class LoraGetLastSubmitTime(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.GET_LAST_SUBMIT_TIME)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 4:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        ts      = int.from_bytes(d[0:4], "little")
        dt_str  = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self._ts = ts
        _log.debug(f"  Last Submit Time: {dt_str} (unix={ts})")
        return f"OK:{dt_str} (unix={ts})"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = LoraGetLastSubmitTime().execute()
    print(result)
    sm.disconnect_all()
