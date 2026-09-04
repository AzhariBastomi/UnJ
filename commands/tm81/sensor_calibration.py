"""
commands/tm81/sensor_calibration.py - Sensor Calibration (CMD 0x02 + 0x04)
Loop: get_config -> get_data -> cek status bit -> ulangi sampai sukses atau
batas Forward pulse tercapai / dibatalkan.

Kondisi stop:
  - OK    : status bit kalibrasi sukses
  - NG    : fwd_pulse > max_fwd_pulse (default 10) — terlalu banyak pulsa
  - NG    : cancel_calibration() dipanggil (tombol Stop / Stop sequence)
  - NG    : safety timeout 300s (failsafe, seharusnya tidak pernah tercapai
            jika max_fwd_pulse sudah diset wajar)

max_fwd_pulse dapat dioverride lewat params={"max_fwd_pulse": N} di JSON.

Selama loop berjalan, keepalive ping (controllers/keepalive.py) di-pause
supaya tidak berebut akses serial port yang sama dengan polling
SENSOR_GET_CONFIG/SENSOR_GET_DATA di sini.
"""

import logging
import threading

_log = logging.getLogger(__name__)

# ── Module-level cancel event (sama polanya dengan _PAUSE_EVT di keepalive) ──
# cancel_calibration() dipanggil oleh:
#   - Tombol Stop pada row kalibrasi (via item.cancel_fn)
#   - TestController.stop_now() untuk membatalkan kalibrasi saat Stop sequence
_CANCEL_EVT = threading.Event()


def cancel_calibration() -> None:
    """Batalkan loop kalibrasi yang sedang berjalan. Thread-safe."""
    _CANCEL_EVT.set()
    _log.debug("[cal] cancel_calibration() dipanggil")


try:
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81.sensor_get_data import SensorGetData
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId
    from commands.tm81.sensor_get_data import SensorGetData


class SensorCalibration(TM81Command):

    CAL_STATUS_FAIL        = 0x01
    CAL_STATUS_NEVER_CAL   = 0x10
    CAL_STATUS_REMOVED     = 0x04
    CAL_STATUS_METAL       = 0x08
    CAL_STATUS_LOW_VOLTAGE = 0x20

    DEFAULT_MAX_FWD_PULSE = 10   # NG jika fwd_pulse melebihi ini
    SAFETY_TIMEOUT_SEC    = 300  # failsafe mutlak

    def __init__(self, conn=None, timeout=None, params=None):
        super().__init__(conn, timeout)
        p = params or {}
        self._max_fwd_pulse = int(p.get("max_fwd_pulse", self.DEFAULT_MAX_FWD_PULSE))

    def _check_cal_status(self, status_byte: int) -> str:
        """Return "" jika OK, atau pesan error."""
        if status_byte & self.CAL_STATUS_FAIL:
            return "Calibration failed"
        if not (status_byte & self.CAL_STATUS_NEVER_CAL):
            return "Never calibrated"
        if status_byte & self.CAL_STATUS_REMOVED:
            return "Sensor removed"
        if status_byte & self.CAL_STATUS_METAL:
            return "Metal interference detected"
        if status_byte & self.CAL_STATUS_LOW_VOLTAGE:
            return "Sensor voltage too low"
        return ""

    @staticmethod
    def _resp_cmd(r) -> int:
        return r.raw[2] if r.raw and len(r.raw) >= 3 else -1

    def execute(self) -> str:
        import time

        # _CANCEL_EVT dibersihkan oleh run_fn di loaders/tm81.py sebelum
        # memanggil execute() — BUKAN di sini, supaya retry tidak mengabaikan cancel

        try:
            from controllers.keepalive import pause_global, resume_global
            _ka = True
        except ImportError:
            _ka = False

        if _ka:
            pause_global()
            _log.debug("  [cal] keepalive ping dijeda selama kalibrasi")

        _result: list = [None]

        def _bg():
            try:
                _result[0] = self._run_loop()
            finally:
                # resume_global di sini supaya keepalive baru aktif kembali
                # setelah xfer yang sedang berjalan benar-benar selesai,
                # meski execute() sudah return lebih dulu karena cancel.
                if _ka:
                    resume_global()
                    _log.debug("  [cal] keepalive ping dilanjutkan")

        t = threading.Thread(target=_bg, daemon=True, name="cal-loop")
        t.start()

        # Poll setiap 50ms — return segera saat cancel tanpa tunggu xfer selesai
        while t.is_alive():
            if _CANCEL_EVT.is_set():
                _log.debug("  [cal] execute() return segera — bg thread selesaikan xfer sendiri")
                return "NG:Kalibrasi dibatalkan"
            time.sleep(0.05)

        return _result[0] or "NG:Loop selesai tanpa hasil"

    def _run_loop(self) -> str:
        import time as _time

        def _wait(sec: float) -> bool:
            """Tunggu sec detik, atau langsung return True jika cancel di-set."""
            return _CANCEL_EVT.wait(sec)

        def _cancelled() -> "str | None":
            if not _CANCEL_EVT.is_set():
                return None
            _log.debug("  [cal] dibatalkan oleh user")
            fwd = last_info["fwd_pulse"] if last_info else "?"
            bwd = last_info["bwd_pulse"] if last_info else "?"
            return (f"NG:Kalibrasi dibatalkan  |  "
                    f"Forward pulse: {fwd}  Backward pulse: {bwd}")

        deadline  = _time.time() + self.SAFETY_TIMEOUT_SEC
        last_info = None
        attempt   = 0
        last_err  = "belum ada response"

        while _time.time() < deadline:
            msg = _cancelled()
            if msg:
                return msg

            attempt += 1
            if _wait(2):   # tunggu 2s, keluar segera jika cancel
                return _cancelled() or "NG:Dibatalkan"

            # 1. Trigger sensor cycle
            r = self.xfer(CmdId.SENSOR_GET_CONFIG, timeout=3.0)
            if not r.valid and r.error != "ACK":
                last_err = f"sensor_get_config fail: {r.error}"
                _log.debug(f"  [cal] {last_err}")
                if _wait(2):
                    return _cancelled() or "NG:Dibatalkan"
                continue
            if self._resp_cmd(r) != CmdId.SENSOR_GET_CONFIG:
                last_err = f"wrong response cmd=0x{self._resp_cmd(r):02x}"
                _log.debug(f"  [cal] {last_err}, skip")
                if _wait(2):
                    return _cancelled() or "NG:Dibatalkan"
                continue

            if _wait(2):   # tunggu device selesai satu siklus
                return _cancelled() or "NG:Dibatalkan"

            # 2. Baca hasil
            r = self.xfer(CmdId.SENSOR_GET_DATA, timeout=6.0)
            if not r.valid:
                last_err = f"sensor_get_data fail: {r.error}"
                _log.debug(f"  [cal] {last_err}")
                if _wait(2):
                    return _cancelled() or "NG:Dibatalkan"
                continue

            if not r.payload or len(r.payload) < 13:
                last_err = f"payload terlalu pendek ({len(r.payload)} bytes)"
                _log.debug(f"  [cal] {last_err}, retry")
                continue

            info        = SensorGetData.parse_payload(r.payload)
            last_info   = info
            status_byte = info["status_byte"]
            fwd_pulse   = info["fwd_pulse"]
            bwd_pulse   = info["bwd_pulse"]

            _log.debug(f"  [cal] attempt {attempt}: Forward pulse={fwd_pulse}  Backward pulse={bwd_pulse}")

            # Cek batas Forward pulse — jika melebihi max → NG
            if fwd_pulse > self._max_fwd_pulse:
                _log.debug(f"  [cal] NG: fwd_pulse {fwd_pulse} > max {self._max_fwd_pulse}")
                return (f"NG:Forward pulse melebihi batas ({fwd_pulse} > {self._max_fwd_pulse})  |  "
                        f"Backward pulse: {bwd_pulse}")

            err = self._check_cal_status(status_byte)
            if err:
                last_err = err
                _log.debug(f"  [cal] attempt {attempt}: {err}")
                continue

            # Status OK
            _log.debug(f"  [cal] sukses setelah {attempt} percobaan")
            return (f"OK:Calibration successful  |  "
                    f"Forward pulse: {fwd_pulse}  Backward pulse: {bwd_pulse}")

        fwd = last_info["fwd_pulse"] if last_info else "?"
        bwd = last_info["bwd_pulse"] if last_info else "?"
        return (f"NG:Safety timeout {self.SAFETY_TIMEOUT_SEC}s tercapai "
                f"({attempt} percobaan) — status terakhir: {last_err}  |  "
                f"Forward pulse: {fwd}  Backward pulse: {bwd}")


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = SensorCalibration().execute()
    print(result)
    sm.disconnect_all()
