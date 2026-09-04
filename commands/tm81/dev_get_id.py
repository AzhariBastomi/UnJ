"""
commands/tm81/dev_get_id.py — Get Device ID (CMD 0x1B)
Response payload (24 bytes):
  [0:8]  Device EUI (8 bytes binary)
  [8:24] Serial Number (16 bytes ASCII, null-padded)

Side-effects setelah berhasil baca:
  - SN  → context["device_id"] (update field UI via test_loader watcher)
  - EUI → commissioning.json["lora_set_dev_eui"]["dev_eui"]
"""

import logging
import os as _os
_log   = logging.getLogger(__name__)
_ch340 = logging.getLogger("serial_comm.ch340")

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class DevGetId(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.DEV_GET_ID)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 24:
            return f"NG:payload terlalu pendek ({len(d)} bytes, expected 24)"

        eui    = d[0:8].hex().upper()                # "0080E1010101016F"
        sn_raw = d[8:24]
        if all(b == 0xFF for b in sn_raw) or not sn_raw.strip(b"\x00"):
            sn = "Invalid"
        else:
            sn = sn_raw.rstrip(b"\x00").decode("ascii", errors="replace")

        # Update SN ke context (→ UI field via watcher)
        if sn and sn != "Invalid":
            try:
                import sys, os
                _lib = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
                if _lib not in sys.path:
                    sys.path.insert(0, _lib)
                import test_loader
                test_loader.update_context({"device_id": sn})
                _ch340.debug("[DEV_GET_ID] context device_id → %r", sn)
            except Exception as e:
                _ch340.warning("[DEV_GET_ID] gagal update context: %s", e)

        return f"OK:EUI={eui}\nSN={sn}"

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = DevGetId().execute()
    print(result)
    sm.disconnect_all()
