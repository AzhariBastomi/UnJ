"""
commands/tm81/rtc_get_time.py - Get RTC Time (CMD 0x0A)
Response payload (6 bytes): year(2digit), month, day, hour, minute, second.
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


class RtcGetTime(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_GET_TIME)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 6:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        yr, month, day, hr, mn, sec = d[0], d[1], d[2], d[3], d[4], d[5]
        year = 1900 + yr  # device kirim offset dari 1900 (mis. 126 → 2026)
        self._time_str = f"{year}-{month:02d}-{day:02d} {hr:02d}:{mn:02d}:{sec:02d}"
        _log.debug(f"  RTC Time: {self._time_str}")
        return f"OK:{self._time_str}"

    def get_time(self) -> str:
        return getattr(self, "_time_str", "")


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = RtcGetTime().execute()
    print(result)
    sm.disconnect_all()
