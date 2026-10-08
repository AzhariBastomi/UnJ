"""
commands/tm81/lora_cflist.py — Set/Get CF List mask (CMD 112 / 113)

Mask 1 byte, bit i = added channel index i+2 (AS923-2 added set):
  bit0 ch2 921.2 | bit1 ch3 921.8 | bit2 ch4 922.0
  bit3 ch5 922.2 | bit4 ch6 922.4 | bit5 ch7 922.6
Bit 6-7 diabaikan. Mask dipersist di EEPROM page 57 dan dipakai saat join
berikutnya (jadi set dulu, baru join).

Referensi: SWM_Test_Scripts/Src/LoraSetCFList.py, LoraGetCFList.py.
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

# bit -> nama channel, urutan sama dengan ChannelFrequencyList di SWM Lib/Env.py
CF_CHANNELS = ["ch2 921.2", "ch3 921.8", "ch4 922.0",
               "ch5 922.2", "ch6 922.4", "ch7 922.6"]
CF_MASK_ALL = 0x3F


def decode_mask(mask: int) -> list:
    """Nama channel yang aktif di mask (bit 6-7 diabaikan)."""
    return [n for i, n in enumerate(CF_CHANNELS) if mask & (1 << i)]


class LoraSetCFList(TM81Command):
    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._mask = int(p.get("mask", CF_MASK_ALL)) & 0xFF

    def execute(self) -> str:
        result = self.xfer(CmdId.SET_CFLIST, self._mask.to_bytes(1, "little"))
        if not result.valid and result.error != "ACK":
            return f"NG:{result.error}"
        names = decode_mask(self._mask)
        _log.debug(f"  Set CF list mask=0x{self._mask:02X} → OK")
        return (f"OK:Mask 0x{self._mask:02X} ({len(names)} channel: "
                f"{', '.join(names) if names else 'tidak ada'})")


class LoraGetCFList(TM81Command):
    # Balasan 1 byte = mask, bukan ACK/NAK.
    DATA_BYTE_REPLY = True

    def execute(self) -> str:
        result = self.xfer(CmdId.GET_CFLIST)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 1:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        mask  = d[0]
        names = decode_mask(mask)
        self._mask = mask
        _log.debug(f"  CF list mask: 0x{mask:02X} (0b{mask:06b})")

        summary = f"Mask 0x{mask:02X} — {len(names)} channel aktif"
        detail  = "\n".join(
            [f"{n:<12}: {'ON' if mask & (1 << i) else 'off'}"
             for i, n in enumerate(CF_CHANNELS)]
            + [f"Mask         : 0x{mask:02X} (0b{mask:06b})"]
        )
        return f"OK:{summary}\n{detail}"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    assert decode_mask(0x00) == []
    assert decode_mask(CF_MASK_ALL) == CF_CHANNELS
    assert decode_mask(0x0F) == CF_CHANNELS[:4]      # jangan ketuker NAK
    assert decode_mask(0x11) == [CF_CHANNELS[0], CF_CHANNELS[4]]  # jangan ketuker ACK
    assert decode_mask(0xC0) == []                   # bit 6-7 diabaikan

    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    print(LoraSetCFList(params={"mask": CF_MASK_ALL}).execute())
    print(LoraGetCFList().execute())
    sm.disconnect_all()
