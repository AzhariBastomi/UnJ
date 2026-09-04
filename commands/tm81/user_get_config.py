"""
commands/tm81/user_get_config.py - Get User Config (CMD 0x08)
"""

import logging
import os as _os
_log   = logging.getLogger(__name__)
_ch340 = logging.getLogger("serial_comm.ch340")
_COMMISSIONING_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "config", "commissioning.json")

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class UserGetConfig(TM81Command):

    SUBMIT_RATE = {0:"15min",1:"30min",2:"1h",3:"3h",4:"12h",5:"1day",6:"3day",7:"7day"}
    COUNTER_RES = {0:"1L", 1:"10L", 2:"100L"}
    MSG_TYPE    = {0:"Unconfirmed", 1:"Confirmed"}
    ACTIVATION  = {0:"Deactivated", 1:"Activated"}

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_GET_CONFIG)
        if not result.valid:
            return f"NG:{result.error}"

        d = self._raw = result.payload
        if len(d) < 14:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        counter_res   = d[9]
        init_counter  = int.from_bytes(d[1:5], "little") / (10 * 10**counter_res)
        last_counter  = int.from_bytes(d[5:9], "little") / (10 * 10**counter_res)
        tz_val        = int.from_bytes(bytes([d[12]]), signed=True)

        act  = self.ACTIVATION.get(d[0], d[0])
        res  = self.COUNTER_RES.get(counter_res, counter_res)
        rate = self.SUBMIT_RATE.get(d[11], d[11])
        tz   = f"GMT{chr(43) if tz_val>0 else chr(45)}{abs(tz_val)}"
        msg  = self.MSG_TYPE.get(d[13], d[13])

        _log.debug(f"  Activation   : {act}")
        _log.debug(f"  Init usage   : {init_counter:.2f} m3")
        _log.debug(f"  Last usage   : {last_counter:.2f} m3")
        _log.debug(f"  Counter res  : {res}")
        _log.debug(f"  Alarm byte   : 0x{d[10]:02x} ({self._parse_alarm(d[10])})")
        _log.debug(f"  Submit rate  : {rate}")
        _log.debug(f"  Timezone     : {tz}")
        _log.debug(f"  Msg type     : {msg}")

        alarm      = d[10]
        alarm_str  = self._parse_alarm(alarm)
        lines = (
            f"Activation: {act}\n"
            f"Init usage: {init_counter:.2f} m3\n"
            f"Last usage: {last_counter:.2f} m3\n"
            f"Counter res: {res}\n"
            f"Alarm: {alarm_str}\n"
            f"Submit rate: {rate}\n"
            f"Timezone: {tz}\n"
            f"Msg type: {msg}"
        )
        return f"OK:{lines}"

    # Bit 7 → 0 (MSB first)
    _ALARM_BITS = [
        "Low battery",
        "MCU error",
        "Brown out",
        "WDT",
        "Sensor low intensity",
        "Sensor low voltage",
        "Sensor metal interference",
        "Sensor removed",
    ]

    @classmethod
    def _parse_alarm(cls, alarm_byte: int) -> str:
        triggered = [cls._ALARM_BITS[i] for i in range(8) if (alarm_byte >> (7 - i)) & 1]
        return ", ".join(triggered) if triggered else "None"


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserGetConfig().execute()
    print(result)
    sm.disconnect_all()
