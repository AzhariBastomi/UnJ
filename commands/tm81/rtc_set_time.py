"""
commands/tm81/rtc_set_time.py — Set RTC Time (CMD 0x0B)
Data (6 bytes): year(2digit, offset 2000), month, day, hour, minute, second.
"""

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

import datetime


class RtcSetTime(TM81Command):
    """
    Set RTC ke waktu sekarang (PC time) atau waktu custom.

    Contoh:
        RtcSetTime().execute()                     # pakai waktu PC
        RtcSetTime(dt=datetime(2025,1,15,9,0,0)).execute()
    """

    def __init__(self, dt: datetime.datetime = None, **kwargs):
        super().__init__(**kwargs)
        self._dt = dt

    def execute(self) -> str:
        dt = self._dt or datetime.datetime.now()
        data = bytes([
            dt.year - 2000, dt.month, dt.day,  # 2-digit year: offset dari 2000
            dt.hour, dt.minute, dt.second,
        ])
        result = self.xfer(CmdId.USR_SET_TIME, data=data)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        return f"OK:{time_str}"


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    # Tanpa argumen: pakai waktu PC sekarang
    # RtcSetTime(dt=datetime.datetime(2025,1,15,9,0,0)).execute()
    result = RtcSetTime().execute()
    print(result)
    sm.disconnect_all()
