"""
controllers/test_controller.py — Orchestrates running tests + DB upload.
"""

import logging
import os
import sys
import threading
import time

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import json
from test_modules import TestResult
import test_loader

log = logging.getLogger("controller")


class TestController:
    """Orchestrates running individual tests or all tests in sequence."""

    def __init__(self):
        self._serial      = None
        self._seq_running = False
        self._stop_event  = threading.Event()
        self._wf          = self._load_workflow()
        self._uploader    = None   # UploaderBase instance, set by App

        # Factory/Strategy registry — dipilih berdasar item.type_key, bukan
        # if/elif per TestType. Dipakai hanya untuk item TANPA run_fn (mis.
        # test bawaan demo); item TM81/BEXA selalu punya run_fn sendiri.
        self._runner_registry = {
            "progress": self._run_progress,
            "manual":   self._run_manual,
            "auto":     self._run_auto,
        }

    @staticmethod
    def _load_workflow() -> dict:
        try:
            path = os.path.join(_ROOT, "config", "config.json")
            with open(path) as f:
                return json.load(f).get("workflow", {})
        except Exception:
            return {}

    @property
    def _test_delay(self) -> float:
        return self._wf.get("test_delay_ms", 500) / 1000.0

    @property
    def _max_retries(self) -> int:
        return max(0, int(self._wf.get("max_retries", 3)))

    @property
    def _retry_delay(self) -> float:
        return self._wf.get("retry_delay_ms", 1000) / 1000.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def is_seq_running(self) -> bool:
        return self._seq_running

    def run_test(self, row, done_callback=None):
        item = row.test_item
        row.set_running()

        if item.run_fn is not None:
            self._run_with_fn(row, done_callback)
            return

        runner = self._runner_registry.get(item.type_key, self._run_auto)
        runner(row, done_callback)

    def _run_with_fn(self, row, done_callback):
        item = row.test_item

        def _progress(pct):
            row.master.after(0, lambda p=pct: row.advance_progress(p))

        fn = item.run_fn
        # Dua bentuk run_fn didukung:
        #   - bound method dari TestBase          -> setter di fn.__self__
        #   - closure biasa (mis. loaders/flash)  -> setter ditempel di fn
        setter = None
        if hasattr(fn, "__self__") and hasattr(fn.__self__, "set_progress_cb"):
            setter = fn.__self__.set_progress_cb
        elif hasattr(fn, "set_progress_cb"):
            setter = fn.set_progress_cb

        if setter is not None:
            setter(_progress)
        else:
            log.warning("run_fn '%s' tidak punya set_progress_cb — "
                        "progress bar tidak akan bergerak", item.title)

        max_retries = 0 if item.no_retry else self._max_retries
        retry_delay = self._retry_delay

        def _try_once():
            try:
                resp = item.run_fn()
            except Exception as e:
                log.exception("Exception saat run_fn '%s':", item.title)
                resp = f"NG:{e}"
            resp = str(resp).strip()
            # expect hanya di-enforce saat Start sequence, bukan Run individual
            if self._seq_running and getattr(item, "expect", None):
                from validation_rules import apply_expect_check
                resp = apply_expect_check(resp, item.expect)
            is_ok  = resp.upper() == "OK" or resp.upper().startswith("OK:")
            ok_msg = resp[3:].strip() if resp.upper().startswith("OK:") else ""
            error  = resp.split(":", 1)[1].strip() if not is_ok and ":" in resp else ""
            return is_ok, error, ok_msg

        def worker():
            t_start = time.monotonic()
            is_ok, error, ok_msg = _try_once()
            for attempt in range(1, max_retries + 1):
                if is_ok or self._stop_event.is_set():
                    break
                row.master.after(0, lambda a=attempt, n=max_retries: row.show_retry(a, n))
                for _ in range(int(retry_delay / 0.05)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.05)
                if self._stop_event.is_set():
                    break
                row.master.after(0, row.set_running)
                is_ok, error, ok_msg = _try_once()

            if self._stop_event.is_set():
                return

            duration_ms = int((time.monotonic() - t_start) * 1000)
            result = TestResult.OK if is_ok else TestResult.NG
            row.master.after(
                0, lambda r=result, e=error, m=ok_msg, d=duration_ms:
                _finish(r, e, m, d)
            )

        def _finish(result, error="", ok_msg="", duration_ms=0):
            row.set_result(result, error, ok_msg)
            if done_callback:
                done_callback(row)
            if self._uploader:
                try:
                    from db_uploader import TestResultRecord
                    rec = TestResultRecord(
                        station=test_loader.get_context("station"),
                        device_id=test_loader.get_context("device_id"),
                        test_name=row.test_item.title,
                        command=getattr(row.test_item, "command", ""),
                        result="OK" if result == TestResult.OK else "NG",
                        duration_ms=duration_ms,
                        notes=error or ok_msg,
                    )
                    threading.Thread(
                        target=self._uploader.upload, args=(rec,), daemon=True
                    ).start()
                except Exception as e:
                    log.warning("Gagal upload ke DB: %s", e)

        threading.Thread(target=worker, daemon=True).start()

    def run_all(self, rows: list, done_callback=None, scroll_fn=None):
        if self._seq_running:
            return
        self._stop_event.clear()
        threading.Thread(
            target=self._seq_worker, args=(rows, done_callback, scroll_fn), daemon=True
        ).start()

    def stop_now(self, rows: list):
        self._stop_event.set()
        self._seq_running = False
        # Batalkan kalibrasi yang mungkin sedang berjalan di background thread
        try:
            from commands.tm81.sensor_calibration import cancel_calibration
            cancel_calibration()
        except ImportError:
            pass
        for row in rows:
            row.reset()

    # ------------------------------------------------------------------
    # Progress / Manual / Auto
    # ------------------------------------------------------------------

    def _run_progress(self, row, done_callback):
        item = row.test_item

        def tick():
            step[0] += 1
            pct = (step[0] / item.steps) * 90
            row.advance_progress(pct)
            if step[0] < item.steps:
                row.master.after(item.step_ms, tick)
            else:
                self._serial.send_command(
                    item.command,
                    callback=lambda resp: _finish(resp),
                    error_callback=lambda e: _finish("NG"),
                )

        step = [0]

        def _finish(resp: str):
            result = TestResult.OK if resp.strip().upper() == "OK" else TestResult.NG
            row.advance_progress(100)
            row.set_result(result)
            if done_callback:
                done_callback(row)

        row.master.after(0, tick)

    def _run_manual(self, row, done_callback):
        log.debug("_run_manual: %s", row.test_item.title)

        def _poll():
            if row.test_item.is_done():
                if done_callback:
                    done_callback(row)
            else:
                row.master.after(200, _poll)

        def _show():
            row.enable_manual_buttons()
            row.master.after(200, _poll)

        row.master.after(0, _show)

    def _run_auto(self, row, done_callback):
        item = row.test_item

        def _on_response(resp: str):
            result = TestResult.OK if resp.strip().upper() == "OK" else TestResult.NG
            row.set_result(result)
            if done_callback:
                done_callback(row)

        self._serial.send_command(
            item.command,
            callback=_on_response,
            error_callback=lambda e: row.set_result(TestResult.NG),
        )

    # ------------------------------------------------------------------
    # Sequential runner
    # ------------------------------------------------------------------

    def _seq_worker(self, rows: list, done_callback, scroll_fn=None):
        self._seq_running = True
        last_row = None

        for row in rows:
            if not self._seq_running:
                break
            if row.test_item.is_done():
                continue

            last_row    = row
            is_manual   = row.test_item.is_manual

            if scroll_fn:
                row.master.after(0, lambda r=row: scroll_fn(r))

            event = threading.Event()
            row.master.after(
                0,
                lambda r=row, ev=event: self.run_test(
                    r, done_callback=lambda _r, ev=ev: ev.set()
                )
            )

            # Timeout per-step: ambil dari test_item (timeout_s), fallback ke
            # config workflow, fallback ke 600 detik (cukup untuk OTA ~3 menit+).
            _default_timeout = self._wf.get("step_timeout_s", 600)
            _item_timeout    = getattr(row.test_item, "timeout_s", None)
            _timeout_s       = _item_timeout if _item_timeout is not None else _default_timeout
            deadline = None if is_manual else (time.time() + _timeout_s)
            while not event.is_set() and not self._stop_event.is_set():
                if deadline and time.time() > deadline:
                    log.warning("Step '%s' melebihi timeout %ds, paksa lanjut",
                                row.test_item.title, _timeout_s)
                    break
                time.sleep(0.05)

            if self._stop_event.is_set():
                break

            if row.test_item.result == TestResult.NG:
                self._seq_running = False
                break

            for _ in range(int(self._test_delay / 0.05)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.05)

        self._seq_running = False
        master = last_row.master if last_row else rows[0].master if rows else None
        if done_callback and master:
            master.after(0, lambda: done_callback(None))
