"""
commands/tm81/lora_get_config.py — Get LoRaWAN Config (CMD 0x16)
Response payload (57 bytes): full LoRaWAN configuration.
"""

import logging
_log   = logging.getLogger(__name__)
_ch340 = logging.getLogger("serial_comm.ch340")

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class LoraGetConfig(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.GET_LORA_DATA)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 10:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        # Layout (57 bytes): class(1)+mode(1)+devaddr(4)+deveui(8)+joineui(8)+appkey(16)+nwkkey(16)+txpower(1)+dr(1)+rx1delay(1)
        class_map    = {0: "A", 1: "B", 2: "C"}
        mode_map     = {0: "NONE", 1: "ABP", 2: "OTAA"}

        config = {
            "lora_class":    class_map.get(d[0], f"unknown({d[0]})"),
            "join_mode":     mode_map.get(d[1], f"unknown({d[1]})"),
            "dev_addr":      f"0x{int.from_bytes(d[2:6], 'little').to_bytes(4,'big').hex()}",
            "dev_eui":       d[6:14].hex(),
            "join_eui":      d[14:22].hex(),
            "app_key":       d[22:38].hex() if len(d) >= 38 else "N/A",
            "nwk_key":       d[38:54].hex() if len(d) >= 54 else "N/A",
            "tx_power":      d[54] if len(d) > 54 else "N/A",
            "data_rate":     d[55] if len(d) > 55 else "N/A",
            "rx1_delay":     d[56] if len(d) > 56 else "N/A",
        }

        self._config = config
        for k, v in config.items():
            _log.debug(f"  {k}: {v}")

        summary = f"Class {config['lora_class']} | {config['join_mode']} | DR{config['data_rate']} | TxPwr {config['tx_power']}"
        detail = "\n".join([
            f"Class      : {config['lora_class']}",
            f"Join Mode  : {config['join_mode']}",
            f"DevAddr    : {config['dev_addr']}",
            f"DevEUI     : {config['dev_eui']}",
            f"JoinEUI    : {config['join_eui']}",
            f"AppKey     : {config['app_key']}",
            f"NwkKey     : {config['nwk_key']}",
            f"TX Power   : {config['tx_power']}",
            f"Data Rate  : {config['data_rate']}",
            f"RX1 Delay  : {config['rx1_delay']}",
        ])
        return f"OK:{summary}\n{detail}"

    def get_config(self) -> dict:
        return getattr(self, "_config", {})

# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = LoraGetConfig().execute()
    print(result)
    sm.disconnect_all()
