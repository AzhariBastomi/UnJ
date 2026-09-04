"""
commands/tm81/lora_force_send.py — Force Send LoRa (CMD 0x17)
Paksa device kirim uplink sekarang.
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


class LoraForceSend(TM81Command):

    _ACK          = 0x11
    _RECOVERY     = 0xE6

    def execute(self) -> str:
        result = self.xfer(CmdId.FORCE_SEND_LORA, timeout=10.0)
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"

        status = result.payload[0] if result.payload else self._ACK
        if status == self._ACK:
            _log.debug("  LoRa Force Send → uplink dikirim")
            return "OK:uplink dikirim"
        elif status == self._RECOVERY:
            _log.debug("  LoRa Force Send → masih dalam recovery period (0xE6)")
            return "NG:masih dalam recovery period — tunggu sebentar lalu coba lagi"
        else:
            _log.debug(f"  LoRa Force Send → status tidak dikenal: 0x{status:02x}")
            return f"NG:status tidak dikenal (0x{status:02x})"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = LoraForceSend().execute()
    print(result)
    sm.disconnect_all()
