"""commands/tm81/user_set_config.py — Set User Config (CMD 0x07)

Kirim:
  activation(1B) + initial_counter(4B) + counter_res(1B) +
  alarm(1B) + submit_id(1B) + timezone(1B) + msg_type(1B)

Defaults: activated, 0, RES_10L, 0, FIFTEEN_MINS, UTC+7, CONFIRMED
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


class UserSetConfig(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._activation    = 1   # selalu ACTIVATED — tujuan set_config adalah aktivasi
        self._counter       = p.get("initial_counter", 0)
        self._counter_res   = p.get("counter_res",   1)   # 1=RES_10L
        self._alarm         = p.get("alarm",         0)
        self._submit_id     = p.get("submit_id",     0)   # 0=FIFTEEN_MINS
        self._timezone      = p.get("timezone",      7)   # UTC+7
        self._msg_type      = p.get("msg_type",      1)   # 1=CONFIRMED

    def execute(self) -> str:
        data = (
            self._activation.to_bytes(1, "little")
            + self._counter.to_bytes(4, "little")
            + self._counter_res.to_bytes(1, "little")
            + self._alarm.to_bytes(1, "little")
            + self._submit_id.to_bytes(1, "little")
            + self._timezone.to_bytes(1, "little", signed=True)   # signed: support UTC negatif
            + self._msg_type.to_bytes(1, "little")
        )
        result = self.xfer(CmdId.USR_SET_CFG, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        SUBMIT = {0:"15min",1:"30min",2:"1h",3:"3h",4:"12h",5:"1day",6:"3day",7:"7day"}
        CRES   = {0:"1L",1:"10L",2:"100L"}
        ACT    = {0:"Deactivated",1:"Activated"}
        MSG    = {0:"Unconfirmed",1:"Confirmed"}
        tz_sign = "+" if self._timezone >= 0 else ""

        act    = ACT.get(self._activation, self._activation)
        res    = CRES.get(self._counter_res, self._counter_res)
        submit = SUBMIT.get(self._submit_id, self._submit_id)
        msg    = MSG.get(self._msg_type, self._msg_type)

        # Baris pertama = ringkasan singkat (tampil di row UI)
        brief = f"Activation: {act}  |  TZ: UTC{tz_sign}{self._timezone}"

        # Detail: satu field per baris (tampil saat di-klik)
        detail = "\n".join([
            f"Activation   : {act}",
            f"Init counter : {self._counter}",
            f"Counter res  : {res}",
            f"Alarm        : {self._alarm:#04x}",
            f"Submit rate  : {submit}",
            f"Timezone     : UTC{tz_sign}{self._timezone}",
            f"Msg type     : {msg}",
        ])
        _log.debug(f"  User Set Config → OK  {brief}")
        return f"OK:{brief}\n{detail}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    # activation=1, initial_counter=0, alarm=0, timezone=7
    params = {}
    result = UserSetConfig(params=params).execute()
    print(result)
    sm.disconnect_all()
