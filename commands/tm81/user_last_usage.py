"""
commands/tm81/user_last_usage.py — Hitung Last Usage dari sensor + user config

Flow:
  1. SENSOR_GET_CONFIG  — trigger satu siklus sensor
  2. Tunggu 2s          — beri device waktu menyelesaikan siklus
  3. SENSOR_GET_DATA    — baca Forward pulse + Backward pulse
  4. USER_GET_CONFIG    — baca initial_counter (raw) + counter_res
  5. Hitung:
       net_pulse     = fwd_pulse - bwd_pulse
       init_usage_m3 = initial_counter_raw / (10 × 10^counter_res)
       last_usage_m3 = init_usage_m3 + net_pulse × 10^counter_res / 1000

Contoh counter_res=1 (10L/pulse):
  init_counter_raw=584 → 584/100 = 5.84 m3
  net_pulse=111        → 111×10/1000 = 1.11 m3
  last_usage           = 5.84 + 1.11 = 6.95 m3
"""

import logging
import time

_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81.sensor_get_data import SensorGetData
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81.sensor_get_data import SensorGetData


class UserLastUsage(TM81Command):

    COUNTER_RES = {0: "1L", 1: "10L", 2: "100L"}

    def execute(self) -> str:
        # ── 1. Trigger sensor cycle ────────────────────────────────────────
        r = self.xfer(CmdId.SENSOR_GET_CONFIG, timeout=3.0)
        if not r.valid and r.error != "ACK":
            return f"NG:Sensor Get Config gagal — {r.error}"
        _log.debug("  [last_usage] SENSOR_GET_CONFIG → OK")

        # ── 2. Tunggu sensor selesai satu siklus ──────────────────────────
        time.sleep(2.0)

        # ── 3. Baca sensor data ────────────────────────────────────────────
        r = self.xfer(CmdId.SENSOR_GET_DATA, timeout=6.0)
        if not r.valid:
            return f"NG:Sensor Get Data gagal — {r.error}"
        if not r.payload or len(r.payload) < 14:
            return f"NG:Sensor payload terlalu pendek ({len(r.payload) if r.payload else 0} bytes)"

        info      = SensorGetData.parse_payload(r.payload)
        fwd_pulse = info["fwd_pulse"]
        bwd_pulse = info["bwd_pulse"]
        net_pulse = fwd_pulse - bwd_pulse
        _log.debug("  [last_usage] fwd=%d  bwd=%d  net=%d", fwd_pulse, bwd_pulse, net_pulse)

        # ── 4. Baca User Config ────────────────────────────────────────────
        r = self.xfer(CmdId.USR_GET_CONFIG, timeout=3.0)
        if not r.valid:
            return f"NG:User Get Config gagal — {r.error}"
        d = r.payload
        if not d or len(d) < 14:
            return f"NG:User config payload terlalu pendek ({len(d) if d else 0} bytes)"

        counter_res      = d[9]
        init_counter_raw = int.from_bytes(d[1:5], "little")
        last_counter_raw = int.from_bytes(d[5:9], "little")   # last usage dari device

        # ── 5. Hitung last usage ───────────────────────────────────────────
        #   Resolusi: 10^counter_res liter per pulse
        #   m3 per pulse = 10^counter_res / 1000
        res_L             = 10 ** counter_res
        init_usage_m3     = init_counter_raw / (10 * 10 ** counter_res)
        last_device_m3    = last_counter_raw / (10 * 10 ** counter_res)  # dari device
        net_volume_m3     = net_pulse * res_L / 1000
        last_computed_m3  = init_usage_m3 + net_volume_m3                # dari perhitungan

        res_label = self.COUNTER_RES.get(counter_res, f"{res_L}L")

        _log.debug("  [last_usage] init_raw=%d  last_raw=%d  counter_res=%d (%s)",
                   init_counter_raw, last_counter_raw, counter_res, res_label)
        _log.debug("  [last_usage] init=%.3f m3  net_vol=%.3f m3",
                   init_usage_m3, net_volume_m3)
        _log.debug("  [last_usage] last (device)=%.3f m3  last (hitung)=%.3f m3",
                   last_device_m3, last_computed_m3)

        brief = f"Dev: {last_device_m3:.2f}  Hitung: {last_computed_m3:.2f} m3"
        detail = "\n".join([
            f"Forward pulse       : {fwd_pulse}",
            f"Backward pulse      : {bwd_pulse}",
            f"Net pulse           : {net_pulse}",
            f"Counter res         : {res_label}",
            f"Init usage          : {init_usage_m3:.3f} m3",
            f"Net volume          : {net_volume_m3:.3f} m3",
            f"Last usage (device) : {last_device_m3:.3f} m3",
            f"Last usage (hitung) : {last_computed_m3:.3f} m3",
        ])
        return f"OK:{brief}\n{detail}"


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserLastUsage().execute()
    print(result)
    sm.disconnect_all()
