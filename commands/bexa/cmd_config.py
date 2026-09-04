"""
commands/bexa/cmd_config.py — Command Frame requests.

  ConfigRequest   (0x00) — Request konfigurasi device: sensor rows/cols, versi, status peripheral
  BatteryRequest  (0x05) — Baca status charging dan level baterai
"""

try:
    from commands.bexa.base import BexaCommand, CmdID
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.bexa.base import BexaCommand, CmdID

import struct


# Bit-map Peripheral Status (byte, MSB ke LSB):
# [7:unused][6:unused][5:BT][4:TACTILE][3:CC][2:IMU][1:HAPTIC_LR][0:TLC5940]
_PERIPHERAL_BITS = {
    5: "BT",
    4: "TACTILE",
    3: "CC",
    2: "IMU",
    1: "HAPTIC",
    0: "TLC5940",
}


def _parse_peripheral_status(status_byte: int) -> str:
    parts = []
    for bit, name in sorted(_PERIPHERAL_BITS.items(), reverse=True):
        val = (status_byte >> bit) & 0x01
        parts.append(f"{name}={'OK' if val else 'FAIL'}")
    return "  ".join(parts)


class ConfigRequest(BexaCommand):
    """
    Command 0x00 — Config Request.

    Kirim Protocol Version, device balas dengan:
      Sensor_Row, Sensor_Cols, Sensor_Version(2B), Position_Length,
      Protocol_Version, Peripheral_Status, Firmware_Version
    """

    TIMEOUT = 5.0

    def execute(self) -> str:
        # Payload: Protocol Version (1 byte) — kirim versi 0x01
        payload = bytes([0x01])
        r = self.xfer_cmd(CmdID.CONFIG_REQUEST, payload, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"

        d = r.payload
        if len(d) < 7:
            return f"OK:Config ACK (payload pendek: {d.hex(' ')})"

        sensor_row  = d[0]
        sensor_cols = d[1]
        sensor_ver  = struct.unpack_from("<H", d, 2)[0]
        pos_len     = d[4]
        proto_ver   = d[5]
        periph_stat = d[6]
        fw_ver      = d[7:] if len(d) > 7 else b""

        periph_str = _parse_peripheral_status(periph_stat)

        return (f"OK:Sensor={sensor_row}x{sensor_cols}  SensorVer=0x{sensor_ver:04X}  "
                f"ProtoVer={proto_ver}  [{periph_str}]  "
                f"FW={fw_ver.decode('ascii', errors='replace') if fw_ver else 'N/A'}")


class BatteryRequest(BexaCommand):
    """
    Command 0x05 — Battery Request.

    Device balas dengan:
      Charging_State (1B) : 0=not charging, 1=charging, 2=full
      Battery_Level  (1B) : 0-100%
    """

    _STATES = {0: "Not Charging", 1: "Charging", 2: "Full"}

    def execute(self) -> str:
        r = self.xfer_cmd(CmdID.BATTERY_REQUEST)
        if not r.valid:
            return f"NG:{r.error}"

        d = r.payload
        if len(d) < 2:
            return f"OK:Battery ACK (payload: {d.hex(' ')})"

        state = d[0]
        level = d[1]
        state_s = self._STATES.get(state, f"State={state}")
        brief = f"{state_s}  |  Level: {level}%"
        detail = "\n".join([
            f"Charging State: {state_s}",
            f"Battery Level : {level}%",
        ])
        return f"OK:{brief}\n{detail}"
