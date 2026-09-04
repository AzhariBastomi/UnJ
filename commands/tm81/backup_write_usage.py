"""commands/tm81/backup_write_usage.py — Tulis usage history (CMD 0x19)

day=0 → tulis seluruh bulan (31 entries × 4B dari whole_month_usage_m3)
day>0 → tulis satu hari saja (daily_usage_m3)
"""
try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId
from datetime import datetime
import logging
_log = logging.getLogger(__name__)


class BackupWriteUsage(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        now = datetime.now()
        self._day              = p.get("day",   1)
        self._month            = p.get("month", now.month)
        self._year             = p.get("year",  now.year)
        self._daily_usage_m3   = p.get("daily_usage_m3",  0.0)
        self._monthly_usage_m3 = p.get("whole_month_usage_m3", [0.0] * 31)

    def execute(self) -> str:
        year_b = (self._year - 2000).to_bytes(1, "little")
        is_monthly = (self._day == 0)

        if is_monthly:
            payload = b""
            for v in self._monthly_usage_m3:
                payload += int(round(v, 2) * 100).to_bytes(4, "little")
            data = payload
        else:
            daily_int = int(round(self._daily_usage_m3, 2) * 100)
            data = (
                self._day.to_bytes(1, "little")
                + self._month.to_bytes(1, "little")
                + year_b
                + daily_int.to_bytes(4, "little")
            )

        result = self.xfer(CmdId.USAGE_HISTORY_WRITE, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        _log.debug("  Backup Write Usage → OK")
        return "OK"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    # params: day, month, pulse_res
    params = {}  # kosongkan untuk default
    result = BackupWriteUsage(params=params).execute()
    print(result)
    sm.disconnect_all()
