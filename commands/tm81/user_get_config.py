"""
commands/tm81/user_get_config.py - Get User Config (CMD 0x08)

Response payload — alarm_status firmware baru 2 byte (u16 LE), payload
14 -> 15 byte, jadi submit_rate/timezone/msg_type bergeser 1 byte. Layout
dibedakan dari panjang payload: len >= 15 -> alarm u16 (o = 12), selain itu
-> alarm u8 (o = 11).

  [0]      Activation status
  [1-4]    Initial counter (u32 LE)
  [5-8]    Last counter (u32 LE)
  [9]      Counter resolution
  [10-11]  Alarm status (u16 LE; layout lama: [10] saja)
  [o+0]    Submit rate
  [o+1]    Timezone (signed)
  [o+2]    Preferred message type

Referensi: SWM_Test_Scripts/Src/UserGetConfig.py
           SWM_Test_Scripts/Lib/Env.py (TSM_SCP_RESP_LEN_USR_CFG = 15,
                                        AlarmStatusID)
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

        alarm, o = self._layout(d)

        counter_res   = d[9]
        init_counter  = int.from_bytes(d[1:5], "little") / (10 * 10**counter_res)
        last_counter  = int.from_bytes(d[5:9], "little") / (10 * 10**counter_res)
        tz_val        = int.from_bytes(bytes([d[o + 1]]), signed=True)

        act  = self.ACTIVATION.get(d[0], d[0])
        res  = self.COUNTER_RES.get(counter_res, counter_res)
        rate = self.SUBMIT_RATE.get(d[o], d[o])
        tz   = f"GMT{chr(43) if tz_val>0 else chr(45)}{abs(tz_val)}"
        msg  = self.MSG_TYPE.get(d[o + 2], d[o + 2])

        _log.debug(f"  Activation   : {act}")
        _log.debug(f"  Init usage   : {init_counter:.2f} m3")
        _log.debug(f"  Last usage   : {last_counter:.2f} m3")
        _log.debug(f"  Counter res  : {res}")
        _log.debug(f"  Alarm        : 0x{alarm:04x} ({self._parse_alarm(alarm)})")
        _log.debug(f"  Submit rate  : {rate}")
        _log.debug(f"  Timezone     : {tz}")
        _log.debug(f"  Msg type     : {msg}")

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

    @staticmethod
    def _layout(d) -> tuple:
        """(alarm, o) — alarm_status firmware baru 2 byte (u16 LE), payload
        14 -> 15, jadi submit/timezone/msg_type bergeser 1 byte. Dibedakan
        dari panjang payload."""
        if len(d) >= 15:
            return d[10] | (d[11] << 8), 12
        return d[10], 11

    # Bit 0 → 11, urutan sama dengan AlarmStatusID di SWM Lib/Env.py.
    # Bit 8-11 cuma ada di alarm 2 byte (firmware baru).
    _ALARM_BITS = [
        "Sensor removed",
        "Sensor metal interference",
        "Sensor low voltage",
        "Sensor low intensity",
        "WDT",
        "Brown out",
        "MCU error",
        "Low battery",
        "Parity error",
        "Hardware reset",
        "Battery SOH unhealthy",
        "Battery removed",
    ]

    @classmethod
    def _parse_alarm(cls, alarm: int) -> str:
        triggered = [n for i, n in enumerate(cls._ALARM_BITS) if alarm & (1 << i)]
        return ", ".join(triggered) if triggered else "None"


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    # layout baru (15B, alarm u16) vs lama (14B, alarm u8)
    assert UserGetConfig._layout(bytes(10) + bytes([0x10, 0x08]) + bytes(3)) == (0x0810, 12)
    assert UserGetConfig._layout(bytes(10) + bytes([0x10]) + bytes(3)) == (0x10, 11)
    # bit 0 = sensor removed, bit 4 = WDT, bit 11 = battery removed
    assert UserGetConfig._parse_alarm(0) == "None"
    assert UserGetConfig._parse_alarm(1 << 4) == "WDT"
    assert UserGetConfig._parse_alarm(1 | (1 << 11)) == "Sensor removed, Battery removed"

    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserGetConfig().execute()
    print(result)
    sm.disconnect_all()
