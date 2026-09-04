"""
commands/tm81/sensor_get_data.py - Get Sensor Data (CMD 0x04)

Response payload (14 bytes):
  [0:2]  Versi sensor (major, minor)
  [2]    Signal intensity (8 bit rendah)
  [3]    Signal indication (bit0-6) + bit7 = ekstensi MSB signal intensity (9 bit total)
  [4:8]  Forward pulse count  (4 bytes, little-endian)
  [8:12] Backward pulse count (4 bytes, little-endian)
  [12]   Status byte:
           bit0 = kalibrasi gagal
           bit1 = sampling mode (1=fast, 0=slow)
           bit2 = smart module removed
           bit3 = ada interferensi metal
           bit4 = pernah dikalibrasi
           bit5 = tegangan sensor rendah
  [13]   Debug byte:
           bit0 = filter mode dipakai
           bit1 = threshold offset dipakai

Layout ini disamakan dengan reference script SWM_Test_Scripts/Src/SensorGetData.py.
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


class SensorGetData(TM81Command):

    @staticmethod
    def parse_payload(d: bytes) -> dict:
        """Decode payload 14-byte SENSOR_GET_DATA jadi dict field lengkap.
        Dipakai bersama oleh execute() di sini dan oleh SensorCalibration
        (supaya logic decode-nya satu tempat saja, tidak duplikat)."""
        version        = f"{d[0]}.{d[1]}"
        sig_ind_raw    = d[3]
        sig_indication = sig_ind_raw & 0x7F
        sig_intensity  = d[2] | ((sig_ind_raw & 0x80) << 1)  # 9 bit: bit7 sig_ind = MSB tambahan
        fwd_pulse      = int.from_bytes(d[4:8], "little")
        bwd_pulse      = int.from_bytes(d[8:12], "little")
        status         = d[12]
        debug          = d[13]

        return {
            "version":           version,
            "sig_intensity":     sig_intensity,
            "sig_indication":    sig_indication,
            "fwd_pulse":         fwd_pulse,
            "bwd_pulse":         bwd_pulse,
            "status_byte":       status,
            "debug_byte":        debug,
            "cal_failed":        bool(status & 0x01),
            "sampling_mode":     "fast sampling" if status & 0x02 else "slow sampling",
            "module_removed":    bool(status & 0x04),
            "metal_interf":      bool(status & 0x08),
            "ever_calibrated":   bool(status & 0x10),
            "voltage_low":       bool(status & 0x20),
            "filter_mode_used":  bool(debug & 0x01),
            "threshold_used":    bool(debug & 0x02),
        }

    @staticmethod
    def format_detail(info: dict) -> str:
        """Format dict hasil parse_payload() jadi teks detail satu-field-per-baris."""
        yn = lambda b: "yes" if b else "no"
        return "\n".join([
            f"Version              : {info['version']}",
            f"Signal Intensity     : {info['sig_intensity']}",
            f"Signal Indication    : {info['sig_indication']}",
            f"Forward Pulse        : {info['fwd_pulse']}",
            f"Backward Pulse       : {info['bwd_pulse']}",
            f"Calibration Failed   : {yn(info['cal_failed'])}",
            f"Sampling Mode        : {info['sampling_mode']}",
            f"Smart Module Removed : {yn(info['module_removed'])}",
            f"Metal Interference   : {yn(info['metal_interf'])}",
            f"Ever Calibrated      : {yn(info['ever_calibrated'])}",
            f"Voltage Low          : {yn(info['voltage_low'])}",
            f"Filter Mode Used     : {yn(info['filter_mode_used'])}",
            f"Threshold Offset Used: {yn(info['threshold_used'])}",
        ])

    def execute(self) -> str:
        result = self.xfer(CmdId.SENSOR_GET_DATA)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        self._raw_payload = d

        # Kompatibilitas lama: raw 2-byte value (sig_intensity+sig_indication).
        if len(d) >= 2:
            self._raw = int.from_bytes(d[0:2], "little")
        else:
            self._raw = 0

        if len(d) < 14:
            return f"NG:payload terlalu pendek ({len(d)} bytes, expected 14)"

        info = self.parse_payload(d)

        self._version         = info["version"]
        self._sig_intensity   = info["sig_intensity"]
        self._sig_indication  = info["sig_indication"]
        self._fwd_pulse       = info["fwd_pulse"]
        self._bwd_pulse       = info["bwd_pulse"]
        self._status_byte     = info["status_byte"]
        self._debug_byte      = info["debug_byte"]
        self._cal_failed      = info["cal_failed"]
        self._ever_calibrated = info["ever_calibrated"]
        self._module_removed  = info["module_removed"]
        self._metal_interf    = info["metal_interf"]
        self._voltage_low     = info["voltage_low"]

        yn = lambda b: "yes" if b else "no"
        _log.debug(f"  Version: {info['version']}")
        _log.debug(f"  Signal intensity: {info['sig_intensity']}")
        _log.debug(f"  Signal indication: {info['sig_indication']}")
        _log.debug(f"  Forward pulse: {info['fwd_pulse']}")
        _log.debug(f"  Backward pulse: {info['bwd_pulse']}")
        _log.debug(f"  Is calibration failed: {yn(info['cal_failed'])}")
        _log.debug(f"  Sampling mode: {info['sampling_mode']}")
        _log.debug(f"  Is smart module removed: {yn(info['module_removed'])}")
        _log.debug(f"  Is any metal interference: {yn(info['metal_interf'])}")
        _log.debug(f"  Is ever calibrated: {yn(info['ever_calibrated'])}")
        _log.debug(f"  Is voltage low: {yn(info['voltage_low'])}")
        _log.debug(f"  Is filter mode used: {yn(info['filter_mode_used'])}")
        _log.debug(f"  is treshold offset used: {yn(info['threshold_used'])}")

        brief  = f"Ver: {info['version']}  |  SigInt: {info['sig_intensity']}  |  Fwd: {info['fwd_pulse']}  Bwd: {info['bwd_pulse']}"
        detail = self.format_detail(info)
        return f"OK:{brief}\n{detail}"

    def get_raw(self) -> int:
        return getattr(self, "_raw", 0)

    def get_status_byte(self) -> int:
        return getattr(self, "_status_byte", 0)


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = SensorGetData().execute()
    print(result)
    sm.disconnect_all()
