"""commands/tm81/mock_activation.py — Mock Activation test

Langkah:
  1. RtcSetTime (sync ke PC)
  2. UserSetConfig (set config default)
  3. Poll DevGetInfo sampai join_status=1 AND uplink_status=1

Max retries: 12 × 10 detik = 120 detik
"""
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId

import time
from commands.tm81.rtc_set_time import RtcSetTime
from commands.tm81.user_set_config import UserSetConfig
from commands.tm81.dev_get_info import DevGetInfo
import logging
_log = logging.getLogger(__name__)


class MockActivation(TM81Command):
    MAX_RETRIES       = 12
    POLL_INTERVAL_SEC = 10
    IDX_JOIN_STATUS   = 18
    IDX_UPLINK_STATUS = 19

    def execute(self) -> str:
        # Step 1: sync RTC
        r = RtcSetTime(conn=self._conn).execute()
        if r != "OK":
            return f"NG:RtcSetTime {r}"

        # Step 2: set user config
        r = UserSetConfig(conn=self._conn).execute()
        if r != "OK":
            return f"NG:UserSetConfig {r}"

        # Step 3: poll DevGetInfo
        get_info = DevGetInfo(conn=self._conn)
        for attempt in range(1, self.MAX_RETRIES + 1):
            r = get_info.execute()
            if r != "OK":
                return f"NG:DevGetInfo {r}"

            d = get_info._last_payload
            if d is None or len(d) <= max(self.IDX_JOIN_STATUS, self.IDX_UPLINK_STATUS):
                return "NG:payload terlalu pendek"

            join_st   = d[self.IDX_JOIN_STATUS]
            uplink_st = d[self.IDX_UPLINK_STATUS]
            _log.debug(f"  [{attempt}/{self.MAX_RETRIES}] Join={join_st} Uplink={uplink_st}")

            if join_st == 1 and uplink_st == 1:
                _log.debug("  Activation sukses!")
                return "OK"

            if attempt < self.MAX_RETRIES:
                time.sleep(self.POLL_INTERVAL_SEC)

        return "NG:Activation timeout (120s)"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = MockActivation().execute()
    print(result)
    sm.disconnect_all()
