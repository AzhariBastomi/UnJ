"""commands/tm81/lora_set_config.py — Set LoRa Config (CMD 0x1D)

Kirim: tx_power(1B) + data_rate(1B) + rx1_delay_sec(1B)
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


class LoraSetConfig(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._tx_power    = p.get("tx_power",    0)
        self._data_rate   = p.get("data_rate",   2)
        self._rx1_delay   = p.get("rx1_delay",   2)

    def execute(self) -> str:
        data = (
            self._tx_power.to_bytes(1, "little")
            + self._data_rate.to_bytes(1, "little")
            + self._rx1_delay.to_bytes(1, "little")
        )
        result = self.xfer(CmdId.SET_LORA_DATA, data)
        if not result.valid and result.error not in ("ACK",):
            return f"NG:{result.error}"
        brief = f"TxPwr: {self._tx_power}  |  DR: {self._data_rate}  |  RX1Delay: {self._rx1_delay}s"
        detail = "\n".join([
            f"TX Power   : {self._tx_power}",
            f"Data Rate  : {self._data_rate}",
            f"RX1 Delay  : {self._rx1_delay}s",
        ])
        _log.debug(f"  Set LoRa Config: {brief} → OK")
        return f"OK:{brief}\n{detail}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    # tx_power=0, data_rate=2, rx1_delay=2
    params = {}
    result = LoraSetConfig(params=params).execute()
    print(result)
    sm.disconnect_all()
