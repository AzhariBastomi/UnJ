"""
commands/bexa/ftm_sensor.py — FTM Sensor Read commands.

  TactileSensorRead   (0x05) — Baca data Tactile Sensor
  CoulombCounterRead  (0x07) — Baca ACR, Voltage, Temperature
  ImuRead             (0x0C) — Baca data IMU
  ChargingInfo        (0x0F) — Baca info charging
"""

try:
    from commands.bexa.base import BexaCommand, CmdFTM
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.bexa.base import BexaCommand, CmdFTM

import struct


class TactileSensorRead(BexaCommand):
    """FTM 0x05 — Read Tactile Sensor data."""

    TIMEOUT = 8.0  # Sensor mungkin butuh waktu warmup

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.TACTILE_SENSOR_READ, timeout=self.TIMEOUT)
        if not r.valid:
            return f"NG:{r.error}"
        if r.payload:
            return f"OK:Tactile data ({len(r.payload)} bytes) {r.payload.hex(' ')}"
        return "OK:Tactile sensor response diterima"


class CoulombCounterRead(BexaCommand):
    """
    FTM 0x07 — Read Coulomb Counter: ACR, Voltage, Temperature.

    Payload response (expected):
      ACR      : float/int (accumulated charge)
      Voltage  : uint16 (mV)
      Temp     : int16  (0.1°C unit)
    """

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.COULOMB_COUNTER_READ)
        if not r.valid:
            return f"NG:{r.error}"
        d = r.payload
        if len(d) >= 6:
            try:
                voltage = struct.unpack_from("<H", d, 0)[0]
                temp    = struct.unpack_from("<h", d, 2)[0]
                acr     = struct.unpack_from("<H", d, 4)[0]
                brief = f"Voltage: {voltage}mV  |  Temp: {temp/10:.1f}°C  |  ACR: {acr}"
                detail = "\n".join([
                    f"Voltage: {voltage}mV",
                    f"Temp   : {temp/10:.1f}°C",
                    f"ACR    : {acr}",
                ])
                return f"OK:{brief}\n{detail}"
            except Exception:
                pass
        if r.payload:
            return f"OK:Coulomb data {r.payload.hex(' ')}"
        return "OK:Coulomb counter response diterima"


class ImuRead(BexaCommand):
    """
    FTM 0x0C — Read IMU data (accelerometer + gyroscope).

    Payload response (expected, 12 bytes):
      ax, ay, az: int16 (mg)
      gx, gy, gz: int16 (mdps atau raw)
    """

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.IMU_READ)
        if not r.valid:
            return f"NG:{r.error}"
        d = r.payload
        if len(d) >= 12:
            try:
                ax, ay, az = struct.unpack_from("<hhh", d, 0)
                gx, gy, gz = struct.unpack_from("<hhh", d, 6)
                brief = f"Accel: ({ax},{ay},{az})mg  |  Gyro: ({gx},{gy},{gz})"
                detail = "\n".join([
                    f"Accel X: {ax} mg",
                    f"Accel Y: {ay} mg",
                    f"Accel Z: {az} mg",
                    f"Gyro X : {gx}",
                    f"Gyro Y : {gy}",
                    f"Gyro Z : {gz}",
                ])
                return f"OK:{brief}\n{detail}"
            except Exception:
                pass
        if r.payload:
            return f"OK:IMU data {r.payload.hex(' ')}"
        return "OK:IMU response diterima"


class ChargingInfo(BexaCommand):
    """
    FTM 0x0F — Charging Info.

    Payload response (expected):
      charging_state : uint8  (0=not charging, 1=charging, 2=full)
      battery_level  : uint8  (0-100%)
      voltage        : uint16 (mV)
    """

    def execute(self) -> str:
        r = self.xfer_ftm(CmdFTM.CHARGING_INFO)
        if not r.valid:
            return f"NG:{r.error}"
        d = r.payload
        _STATES = {0: "Not Charging", 1: "Charging", 2: "Full"}
        if len(d) >= 2:
            try:
                state   = d[0]
                level   = d[1]
                voltage = struct.unpack_from("<H", d, 2)[0] if len(d) >= 4 else 0
                state_s = _STATES.get(state, f"Unknown({state})")
                brief = f"{state_s}  |  Level: {level}%  |  V: {voltage}mV"
                detail = "\n".join([
                    f"Charging State: {state_s}",
                    f"Battery Level : {level}%",
                    f"Voltage       : {voltage}mV",
                ])
                return f"OK:{brief}\n{detail}"
            except Exception:
                pass
        if r.payload:
            return f"OK:Charging info {r.payload.hex(' ')}"
        return "OK:Charging info response diterima"
