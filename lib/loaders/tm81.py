"""
loaders/tm81.py — Semua TM81 test sources.

TM81OtaTestSource    : flow OTA flash (auto-detected via "fw_version" di root JSON).
TM81GenericTestSource: source reusable untuk semua JSON lain di folder config/ (auto-discovered).

Auto-discovery:
  Semua *.json di commands/tm81/config/ — kecuali commissioning.json dan
  file berawalan "_" (mis. _steps.json) — otomatis di-load tanpa edit
  Python apapun.

  Suite boleh memakai format "tests" (entry lengkap) atau "steps" (ringkas,
  merujuk _steps.json). Resolusinya ada di JsonTestSource.entries().

  Deteksi class:
    "fw_version" di root JSON → TM81OtaTestSource (fw_path resolve + progress_cb).
    JSON lain               → TM81GenericTestSource.

  Override prefix (default = nama file tanpa .json) via field "prefix" di JSON.
  Contoh: tm81_test.json punya "prefix": "tm81" → module name: tm81:get_version.
"""

import json
import logging
import os

from test_base    import TestBase
from test_modules import AutoTest, build_test_item
from validation_rules import build_rule, validation_message

from loaders.base    import JsonTestSource, _ROOT
from loaders.context import get_context
from loaders.flash   import _read_flash_json

_log = logging.getLogger(__name__)

_TM81_CONFIG_DIR    = os.path.join(_ROOT, "commands", "tm81", "config")
_COMMISSIONING_JSON = os.path.join(_TM81_CONFIG_DIR, "commissioning.json")
_TM81_STEPS_JSON    = os.path.join(_TM81_CONFIG_DIR, "_steps.json")

# Bukan suite: commissioning.json, plus semua file berawalan "_"
# (_steps.json dan file pendukung lain di masa depan).
_TM81_MANAGED_JSONS = {"commissioning.json"}

# ---------------------------------------------------------------------------
# Cache commissioning.json — baca ulang hanya jika file berubah (mtime).
# ---------------------------------------------------------------------------
_comm_cache: dict = {}
_comm_mtime: float = 0.0


def _read_commissioning_cached() -> dict:
    """Baca commissioning.json dengan cache per mtime. Thread-safe via GIL."""
    global _comm_cache, _comm_mtime
    try:
        mtime = os.path.getmtime(_COMMISSIONING_JSON)
        if mtime != _comm_mtime:
            try:
                with open(_COMMISSIONING_JSON, encoding="utf-8") as _f:
                    _comm_cache = json.load(_f)
            except Exception:
                _comm_cache = {}
            _comm_mtime = mtime
    except OSError:
        pass
    return _comm_cache


def _read_commissioning_json() -> dict:
    """Baca commissioning.json. Return {} jika belum ada. Di-cache per mtime."""
    return _read_commissioning_cached()


def _merge_commissioning(base: dict) -> dict:
    """Merge commissioning.json (prioritas lebih tinggi) ke atas base commissioning."""
    ext = _read_commissioning_json()
    if not ext:
        return base
    merged = dict(base)
    for key, val in ext.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {
                **merged.get(key, {}),
                **{k: v for k, v in val.items() if not k.startswith("_")},
            }
        else:
            merged[key] = val
    return merged


def _validate_from_commissioning(validate_spec: dict, entry_name: str,
                                  static_params: dict) -> "str | None":
    """Validate params dari commissioning.json. Return pesan error atau None."""
    if not validate_spec:
        return None
    cfg = _read_commissioning_cached()
    sec = cfg.get(entry_name, {})
    for param, raw_rule in validate_spec.items():
        raw = static_params.get(param)
        if raw is None:
            raw = sec.get(param, "")
        if isinstance(raw, str) and raw.startswith("@"):
            raw = get_context(raw[1:])
        val  = str("" if raw is None else raw).strip().replace(":", "").replace(" ", "")
        rule = build_rule(raw_rule)
        if not rule.check(val):
            return f"NG:{validation_message(param, rule)}"
    return None


# ---------------------------------------------------------------------------
# Popup ekstra: Get User Config — bandingkan device vs expect dict di JSON
# ---------------------------------------------------------------------------

def _make_expect_popup_fn(expect_dict: dict):
    """Return popup_extra_fn yang compare device vs expect dict (bukan commissioning)."""
    def _fn(popup, detail_text: str, scale: float, row_widgets: dict = None) -> None:
        import tkinter as tk
        from config import COLORS, BASE_FONTS

        if not expect_dict:
            return

        device = {}
        for line in detail_text.split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                device[k.strip()] = v.strip()

        fs = lambda k: max(7, int(BASE_FONTS[k] * scale))
        C  = COLORS
        bg = C["surface"]

        tk.Frame(popup, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(4, 0))
        hdr = tk.Frame(popup, bg=bg, padx=16, pady=4)
        hdr.pack(fill="x")
        tk.Label(hdr, text="vs Expectation", bg=bg, fg=C["sub"],
                 font=("TkDefaultFont", fs("small"), "bold")).pack(anchor="w")

        for row_key, exp_val in expect_dict.items():
            dev_val = device.get(row_key, "")
            match   = dev_val.lower() == str(exp_val).lower()
            rw = (row_widgets or {}).get(row_key)
            if not rw:
                continue
            rf, _ = rw
            badge = f"  \u2713 match" if match else f"  \u2717 mismatch (exp: {exp_val})"
            color = C["ok"] if match else C["ng"]
            tk.Label(rf, text=badge, bg=bg, fg=color,
                     font=("TkDefaultFont", fs("small"), "bold")).pack(side="left")
    return _fn


# ---------------------------------------------------------------------------
# Popup ekstra: Get User Config — bandingkan device vs commissioning.json
# ---------------------------------------------------------------------------

def _user_get_config_popup_extra(popup, detail_text: str, scale: float,
                                  row_widgets: dict = None) -> None:
    """Tambah badge \u2713/\u2717 inline di detail popup user_get_config."""
    import tkinter as tk
    from config import COLORS, BASE_FONTS

    try:
        with open(_COMMISSIONING_JSON, encoding="utf-8") as f:
            comm = json.load(f).get("user_set_config", {})
    except Exception:
        return
    if not comm:
        return

    device = {}
    for line in detail_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            device[k.strip()] = v.strip()

    COUNTER_RES = {0: "1L",   1: "10L",  2: "100L"}
    SUBMIT_RATE = {0: "15min", 1: "30min", 2: "1h", 3: "3h", 4: "12h",
                   5: "1day", 6: "3day", 7: "7day"}
    MSG_TYPE    = {0: "Unconfirmed", 1: "Confirmed"}

    counter_res_val = comm.get("counter_res", 1)
    res_exp         = counter_res_val if counter_res_val in (0, 1, 2) else 1

    def _init_m3():
        raw = comm.get("initial_counter", 0)
        return f"{raw / (10 * 10**res_exp):.2f} m3"

    def _tz():
        t = comm.get("timezone", 7)
        return f"GMT{'+' if t > 0 else '-'}{abs(t)}"

    mappings = {
        "Counter res": COUNTER_RES.get(counter_res_val, str(counter_res_val)),
        "Submit rate": SUBMIT_RATE.get(comm.get("submit_id", 0), str(comm.get("submit_id", 0))),
        "Timezone":    _tz(),
        "Msg type":    MSG_TYPE.get(comm.get("msg_type", 1), str(comm.get("msg_type", 1))),
        "Init usage":  _init_m3(),
    }

    fs = lambda k: max(7, int(BASE_FONTS[k] * scale))
    C  = COLORS
    bg = C["surface"]

    tk.Frame(popup, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(4, 0))
    hdr = tk.Frame(popup, bg=bg, padx=16, pady=4)
    hdr.pack(fill="x")
    tk.Label(hdr, text="vs Commissioning", bg=bg, fg=C["sub"],
             font=("TkDefaultFont", fs("small"), "bold")).pack(anchor="w")

    for row_key, comm_val in mappings.items():
        dev_val = device.get(row_key, "")
        match   = dev_val.lower() == comm_val.lower()
        rw = (row_widgets or {}).get(row_key)
        if not rw:
            continue
        rf, _ = rw
        badge  = f"  \u2713 match" if match else f"  \u2717 mismatch (exp: {comm_val})"
        color  = C["ok"] if match else C["ng"]
        tk.Label(rf, text=badge, bg=bg, fg=color,
                 font=("TkDefaultFont", fs("small"), "bold")).pack(side="left")


# ---------------------------------------------------------------------------
# Popup ekstra: Get LoRa Config — bandingkan device vs commissioning.json
# ---------------------------------------------------------------------------

def _lora_get_config_popup_extra(popup, detail_text: str, scale: float,
                                  row_widgets: dict = None) -> None:
    """Tambah badge \u2713/\u2717 inline di detail popup lora_get_config."""
    import tkinter as tk
    from config import COLORS, BASE_FONTS

    try:
        with open(_COMMISSIONING_JSON, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return

    CLASS_MAP = {0: "A", 1: "B", 2: "C"}
    MODE_MAP  = {0: "NONE", 1: "ABP", 2: "OTAA"}

    def _fmt_class(v):  return CLASS_MAP.get(v, str(v))
    def _fmt_mode(v):   return MODE_MAP.get(v, str(v))
    def _fmt_hex(v):    return str(v).upper().replace(":", "").replace(" ", "")

    mappings = {}

    dc = cfg.get("lora_set_dev_class", {}).get("dev_class")
    if dc is not None:
        mappings["Class"] = _fmt_class(dc)

    jm = cfg.get("lora_set_join_mode", {}).get("join_mode")
    if jm is not None:
        mappings["Join Mode"] = _fmt_mode(jm)

    eui = get_context("dev_eui") or cfg.get("lora_set_dev_eui", {}).get("dev_eui")
    if eui:
        mappings["DevEUI"] = _fmt_hex(eui)

    jeui = cfg.get("lora_set_join_eui", {}).get("join_eui")
    if jeui:
        mappings["JoinEUI"] = _fmt_hex(jeui)

    lc = cfg.get("lora_set_config", {})
    if "tx_power" in lc:
        mappings["TX Power"] = str(lc["tx_power"])
    if "data_rate" in lc:
        mappings["Data Rate"] = str(lc["data_rate"])
    if "rx1_delay" in lc:
        mappings["RX1 Delay"] = str(lc["rx1_delay"])

    if not mappings:
        return

    device = {}
    for line in detail_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            device[k.strip()] = v.strip()

    fs = lambda k: max(7, int(BASE_FONTS[k] * scale))
    C  = COLORS
    bg = C["surface"]

    tk.Frame(popup, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(4, 0))
    hdr = tk.Frame(popup, bg=bg, padx=16, pady=4)
    hdr.pack(fill="x")
    tk.Label(hdr, text="vs Commissioning", bg=bg, fg=C["sub"],
             font=("TkDefaultFont", fs("small"), "bold")).pack(anchor="w")

    for row_key, comm_val in mappings.items():
        dev_val = device.get(row_key, "")
        match   = _fmt_hex(dev_val) == _fmt_hex(comm_val) or dev_val.lower() == comm_val.lower()
        rw = (row_widgets or {}).get(row_key)
        if not rw:
            continue
        rf, _ = rw
        badge  = "  \u2713 match" if match else f"  \u2717 mismatch (exp: {comm_val})"
        color  = C["ok"] if match else C["ng"]
        tk.Label(rf, text=badge, bg=bg, fg=color,
                 font=("TkDefaultFont", fs("small"), "bold")).pack(side="left")


# ---------------------------------------------------------------------------
# Popup ekstra: Get Last Usage — input meteran referensi + cek toleransi
# ---------------------------------------------------------------------------

def _last_usage_popup_extra(popup, detail_text: str, scale: float,
                            row_widgets: dict = None) -> None:
    """Tambah widget input meteran + perbandingan ke detail popup user_last_usage."""
    import tkinter as tk
    from config import COLORS, BASE_FONTS

    counter_res_l    = 10
    last_device_m3   = None
    last_computed_m3 = None

    for line in detail_text.split("\n"):
        line = line.strip()
        if "Counter res" in line:
            raw = line.split(":")[-1].strip()
            try:
                counter_res_l = int(raw.replace("L", "").strip())
            except ValueError:
                pass
        elif "Last usage (device)" in line:
            raw = line.split(":")[-1].strip()
            try:
                last_device_m3 = float(raw.split()[0])
            except (ValueError, IndexError):
                pass
        elif "Last usage (hitung)" in line:
            raw = line.split(":")[-1].strip()
            try:
                last_computed_m3 = float(raw.split()[0])
            except (ValueError, IndexError):
                pass

    if last_device_m3 is None or last_computed_m3 is None:
        return

    tolerance_m3 = counter_res_l / 1000.0

    fs   = lambda k: max(7, int(BASE_FONTS[k] * scale))
    bg   = COLORS["surface"]
    C    = COLORS

    tk.Frame(popup, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(4, 0))

    cmp = tk.Frame(popup, bg=bg, padx=16, pady=8)
    cmp.pack(fill="x")

    inp = tk.Frame(cmp, bg=bg)
    inp.pack(fill="x", pady=(0, 6))

    tk.Label(inp, text=f"Baca meteran (\u00d7{counter_res_l}L) :",
             bg=bg, fg=C["sub"],
             font=("TkDefaultFont", fs("small")),
             anchor="w").pack(side="left")

    entry_var = tk.StringVar()
    entry = tk.Entry(inp, textvariable=entry_var,
                     font=("TkDefaultFont", fs("small")), width=10)
    entry.pack(side="left", padx=(6, 8))

    _badges: dict = {}

    def _set_badge(row_key: str, text: str, color: str):
        old = _badges.get(row_key)
        if old:
            try:
                old.destroy()
            except Exception:
                pass
        rw = (row_widgets or {}).get(row_key)
        if not rw:
            return
        rf, _ = rw
        b = tk.Label(rf, text=f"  {text}", bg=bg, fg=color,
                     font=("TkDefaultFont", fs("small"), "bold"))
        b.pack(side="left")
        _badges[row_key] = b

    def _check(event=None):
        try:
            raw   = float(entry_var.get().replace(",", "."))
            meter = raw * counter_res_l / 1000.0
        except ValueError:
            _set_badge("Last usage (device)", "? input salah", C["ng"])
            _set_badge("Last usage (hitung)", "? input salah", C["ng"])
            return

        for row_key, val in [
            ("Last usage (device)", last_device_m3),
            ("Last usage (hitung)", last_computed_m3),
        ]:
            diff   = abs(meter - val)
            pulses = round(diff / tolerance_m3, 2)
            ok     = pulses <= 1.0
            _set_badge(row_key,
                       "\u2713 OK" if ok else f"\u2717 NG ({pulses:.1f}p)",
                       C["ok"] if ok else C["ng"])

    tk.Button(inp, text="Cek", command=_check,
              bg=C["header_bg"], fg=C["header_fg"], relief="flat",
              font=("TkDefaultFont", fs("button")),
              padx=8, pady=2, cursor="hand2").pack(side="left")

    entry.bind("<Return>", _check)


# ---------------------------------------------------------------------------
# _TM81FlashStep + TM81OtaTestSource — OTA flash
# ---------------------------------------------------------------------------

class _TM81FlashStep(TestBase):
    """Wrapper agar TestController bisa inject progress_cb ke step OTA."""

    def __init__(self, cmd_cls, conn: str, params: dict, post_wait: float = 0.0,
                 post_popup: str = "", post_popup_s: int = 0,
                 post_popup2: str = "", post_popup_phase2_pct: int = 90):
        super().__init__()
        self._cmd_cls               = cmd_cls
        self._conn                  = conn
        self._params                = params
        self._post_wait             = post_wait
        self._post_popup            = post_popup
        self._post_popup_s          = post_popup_s
        self._post_popup2           = post_popup2
        self._post_popup_phase2_pct = post_popup_phase2_pct

    def run(self) -> str:
        import time as _t
        p = dict(self._params)
        if self._progress_cb:
            p["progress_cb"] = self.report_progress

        try:
            result = self._cmd_cls(conn=self._conn, params=p).execute()
        except Exception as e:
            _log.exception("TM81 Flash step exception:")
            return f"NG:{e}"

        if result == "OK" and self._post_popup and self._post_popup_s > 0:
            from loaders.context import show_countdown_popup
            show_countdown_popup(self._post_popup, self._post_popup_s,
                                 message2=self._post_popup2,
                                 phase2_pct=self._post_popup_phase2_pct)
            _t.sleep(self._post_popup_s)

        if result == "OK" and self._post_wait > 0:
            _t.sleep(self._post_wait)
        return result


class TM81OtaTestSource(JsonTestSource):
    """Test dari tm81_ota*.json.

    Auto-detected: JSON yang punya "fw_version" di root → class ini.
    Resolve fw_path dari fw_version + flash.json (flash_dir)
    + commissioning.json["ota"] (connection, chunk_size, fill_with_ff).
    """

    entity_label = "TM81 Flash step"
    steps_json   = _TM81_STEPS_JSON

    def __init__(self, json_path: str):
        self.json_path = json_path
        self.prefix    = os.path.splitext(os.path.basename(json_path))[0]
        self._cfg      = {}

    def is_enabled(self, entry: dict) -> bool:
        return "name" in entry

    def load_all(self) -> list:
        self._cfg = self.read_json()
        _register_ota_source(self)
        return super().load_all()

    def load_one(self, entry_name: str):
        self._cfg = self.read_json()
        _register_ota_source(self)
        return super().load_one(entry_name)

    def make_item(self, entry: dict):
        name       = entry.get("name", "unknown")
        label      = entry.get("label", name)
        desc       = entry.get("description", "")
        ttype      = entry.get("type", "auto").lower()
        class_path = entry.get("command_class", "")
        post_wait             = float(entry.get("post_wait_s", 0.0))
        post_popup            = entry.get("post_popup", "")
        post_popup_s          = int(entry.get("post_popup_s", 0))
        post_popup2           = entry.get("post_popup2", "")
        post_popup_phase2_pct = int(entry.get("post_popup_phase2_pct", 90))

        comm_ota   = _read_commissioning_json().get("ota", {})
        conn       = comm_ota.get("connection",   "ch340")
        chunk_size = comm_ota.get("chunk_size",   512)
        fill_ff    = comm_ota.get("fill_with_ff", False)

        flash_cfg  = _read_flash_json()
        fw_dir     = os.path.join(_ROOT, flash_cfg.get("flash_dir", "firmware"))

        fw_version = self._cfg.get("fw_version", "")
        if not fw_version:
            fw_path = ""
        elif os.path.isabs(fw_version):
            fw_path = fw_version
        else:
            fw_path = os.path.join(fw_dir, fw_version)

        if "BLWriteFirmware" in class_path or name == "write_fw":
            if not fw_path:
                desc += "\n\u26a0 Belum ada firmware \u2014 buka OTA Settings untuk pilih file"
            elif not os.path.isfile(fw_path):
                desc += f"\n\u26a0 File tidak ditemukan: {os.path.basename(fw_path)}"
            else:
                size_kb = os.path.getsize(fw_path) / 1024
                desc += f"\nFile: {os.path.basename(fw_path)} ({size_kb:.1f} KB)"

        params = {"fw_path": fw_path, "chunk_size": chunk_size, "fill_with_ff": fill_ff}
        # Suite OTA Bootloader (prefix tm81_ota_bl) mengirim image BL — batas
        # ukurannya 32 KB, bukan 160 KB seperti App (lihat bl_tools.fw_max_size).
        if "ota_bl" in (self.prefix or ""):
            params["region"] = "bl"
        params.update(entry.get("params", {}))

        _cmd_cls, _load_err = self.resolve_command_class(class_path)

        if _cmd_cls is None:
            def _err_fn(): return f"NG:{_load_err or 'command_class tidak diset'}"
            return AutoTest(title=label, command=f"TM81_FLASH_{name.upper()}",
                            description=desc, run_fn=_err_fn)

        instance = _TM81FlashStep(_cmd_cls, conn, params, post_wait,
                                  post_popup=post_popup, post_popup_s=post_popup_s,
                                  post_popup2=post_popup2,
                                  post_popup_phase2_pct=post_popup_phase2_pct)

        _expect  = entry.get("expect") or {}
        _run_fn  = instance.run

        kw = dict(title=label, command=f"TM81_FLASH_{name.upper()}",
                  description=desc, run_fn=_run_fn,
                  no_retry=entry.get("no_retry", False))
        if ttype == "progress":
            kw.update(steps=entry.get("steps", 50), step_ms=entry.get("step_ms", 200))
        item = build_test_item(ttype, **kw)
        item.expect = _expect
        return item


# ---------------------------------------------------------------------------
# TM81GenericTestSource — untuk semua JSON (termasuk tm81_test.json)
# ---------------------------------------------------------------------------

class TM81GenericTestSource(JsonTestSource):
    """Source reusable untuk semua TM81 JSON di folder config/.

    Auto-instantiated dari scan folder. Cukup taruh JSON baru di
    commands/tm81/config/ — langsung muncul tanpa edit Python apapun.

    Prefix default = nama file tanpa .json. Override via "prefix" di JSON.
    Contoh: tm81_test.json punya "prefix": "tm81".
    """

    steps_json = _TM81_STEPS_JSON

    def __init__(self, json_path: str):
        stem              = os.path.splitext(os.path.basename(json_path))[0]
        self.json_path    = json_path
        self.entity_label = f"TM81 {stem.replace('_', ' ').title()} test"
        # Baca prefix dari JSON (override stem jika ada)
        try:
            with open(json_path, encoding="utf-8") as f:
                _cfg = json.load(f)
            self.prefix = _cfg.get("prefix", stem)
        except Exception:
            self.prefix = stem

    def make_item(self, entry: dict):
        name          = entry.get("name", "unknown")
        label         = entry.get("label", name)
        desc          = entry.get("description", "")
        cmd_class     = entry.get("command_class", "")
        ttype         = entry.get("type", "auto").lower()
        static_params = entry.get("params", {})
        cmd_prefix    = self.prefix.upper()
        _expect       = entry.get("expect")

        post_wait             = float(entry.get("post_wait_s", 0.0))
        post_popup            = entry.get("post_popup", "")
        post_popup_s          = int(entry.get("post_popup_s", 0))
        post_popup2           = entry.get("post_popup2", "")
        post_popup_phase2_pct = int(entry.get("post_popup_phase2_pct", 90))

        _cmd_cls, _load_err = self.resolve_command_class(cmd_class)
        _ch340 = logging.getLogger("serial_comm.ch340")
        _is_calibration = (name == "sensor_calibration")

        def _run_fn():
            if _cmd_cls is None:
                return f"NG:{_load_err or 'command_class tidak diset'}"
            try:
                if _is_calibration:
                    try:
                        from commands.tm81.sensor_calibration import _CANCEL_EVT
                        _CANCEL_EVT.clear()
                    except ImportError:
                        pass
                commissioning = _merge_commissioning({})
                params = {
                    k: v for k, v in commissioning.get(name, {}).items()
                    if not k.startswith("_")
                }
                params.update(static_params)
                for k, v in list(params.items()):
                    if isinstance(v, str) and v.startswith("@"):
                        params[k] = get_context(v[1:])
                _log.info("[%s] %s", cmd_prefix, label)
                result = _cmd_cls(params=params).execute()
                r = str(result).strip()
                if r.upper().startswith("OK:"):
                    _ch340.debug("[TM81 PARSED] OK  %s", r[3:].split("\n")[0].strip())
                elif r.upper() != "OK":
                    _ch340.debug("[TM81 PARSED] %s", r.split("\n")[0])

                # post_wait_s / post_popup — sama mekanismenya dengan
                # _TM81FlashStep (loaders/tm81.py), cuma dipasang di sini juga
                # supaya suite non-OTA (Gherkin lean/JSON generik) bisa pakai
                # popup countdown yang SAMA (mis. "bl to app") tanpa perlu
                # bikin mekanisme baru.
                _ok = (r.upper() == "OK" or r.upper().startswith("OK:"))
                if _ok and post_popup and post_popup_s > 0:
                    import time as _t
                    from loaders.context import show_countdown_popup
                    show_countdown_popup(post_popup, post_popup_s,
                                         message2=post_popup2,
                                         phase2_pct=post_popup_phase2_pct)
                    _t.sleep(post_popup_s)
                if _ok and post_wait > 0:
                    import time as _t
                    _t.sleep(post_wait)

                return result
            except Exception as e:
                _log.exception("[%s] %s exception:", cmd_prefix, label)
                _ch340.debug("[TM81 PARSED] EXCEPTION: %s", e)
                return f"NG:{e}"

        _validate_spec = entry.get("validate")

        def _validate_fn(spec=_validate_spec, _name=name, _sp=static_params):
            return _validate_from_commissioning(spec, _name, _sp)

        kw = dict(title=label,
                  command=f"{cmd_prefix}_{name.upper()}",
                  description=desc, run_fn=_run_fn,
                  validate_fn=_validate_fn if _validate_spec else None,
                  no_retry=entry.get("no_retry", False))

        if ttype == "progress":
            kw.update(steps=entry.get("steps", 50), step_ms=entry.get("step_ms", 200))

        item = build_test_item(ttype, **kw)
        item.expect = _expect or {}

        if name == "sensor_calibration":
            try:
                from commands.tm81.sensor_calibration import cancel_calibration
                item.cancel_fn = cancel_calibration
            except ImportError:
                pass

        if name == "user_get_config" and _expect:
            item.popup_extra_fn = _make_expect_popup_fn(_expect)
        if name == "user_get_config_post_set":
            item.popup_extra_fn = _user_get_config_popup_extra
        if name in ("lora_get_config", "lora_get_config_post_reset"):
            item.popup_extra_fn = _lora_get_config_popup_extra
        if name == "user_last_usage":
            item.popup_extra_fn = _last_usage_popup_extra

        return item


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

# Registry OTA sources aktif (prefix → instance), di-update saat load_all/load_one.
_active_ota_sources: dict[str, "TM81OtaTestSource"] = {}


def _register_ota_source(src: "TM81OtaTestSource") -> None:
    _active_ota_sources[src.prefix] = src


def get_ota_json_path(prefix: str) -> "str | None":
    """Return json_path OTA source aktif berdasarkan prefix."""
    src = _active_ota_sources.get(prefix)
    return src.json_path if src else None


def _detect_source_class(json_path: str) -> type:
    """Deteksi class yang tepat dari isi JSON.

    "fw_version" di root → TM81OtaTestSource.
    Lainnya             → TM81GenericTestSource.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            cfg = json.load(f)
        if "fw_version" in cfg:
            return TM81OtaTestSource
    except Exception:
        pass
    return TM81GenericTestSource


def _scan_tm81_sources() -> list:
    """Scan folder config, buat source object untuk setiap JSON non-managed.

    Selain source JSON biasa, tiap suite yang punya file features/<stem>.feature
    yang cocok juga dapat satu source Gherkin TAMBAHAN (baris terpisah di Add
    Test, di posisi yang sama) -- urutan/seleksi step-nya dibaca dari .feature,
    isi tiap step tetap dari JSON asli. Lihat loaders/gherkin_common.py.
    """
    sources = []
    try:
        for fname in sorted(os.listdir(_TM81_CONFIG_DIR)):
            if (not fname.endswith(".json")
                    or fname.startswith("_")
                    or fname in _TM81_MANAGED_JSONS):
                continue
            json_path = os.path.join(_TM81_CONFIG_DIR, fname)
            try:
                with open(json_path, encoding="utf-8") as f:
                    _cfg_check = json.load(f)
            except Exception:
                _cfg_check = {}
            if not (_cfg_check.get("steps") or _cfg_check.get("tests")):
                # JSON pengaturan kecil (mis. cuma "fw_version"/"_dialog",
                # tanpa daftar step) -- itu suite OTA "ringkas", daftar
                # step-nya dari <stem>.feature di folder yang sama, sudah
                # ditangani lean scan di bawah (scan_lean_sources ota_only).
                continue
            cls = _detect_source_class(json_path)
            sources.append(cls(json_path))
    except OSError:
        pass

    # Kalau ada features/<stem>.feature yang cocok, GANTI source JSON di
    # posisi yang sama (bukan baris tambahan) -- urutan/seleksi step-nya
    # dibaca dari .feature, isi tiap step tetap dari JSON. Prefix & label
    # tidak berubah, jadi baris di Add Test tetap satu per suite.
    try:
        from loaders.gherkin_common import wrap_if_feature_exists
        for _i, _s in enumerate(sources):
            _g = wrap_if_feature_exists(_s)
            if _g is not None:
                sources[_i] = _g
    except Exception as e:
        _log.warning("Gagal load Gherkin TM81 sources: %s", e)

    # Suite "ringkas" -- HANYA file .feature, tanpa JSON suite sama sekali
    # (lihat loaders/gherkin_lean.py). Berguna kalau suite barunya cuma
    # kombinasi step yang sudah ada, tanpa butuh override apa pun.
    try:
        from loaders.gherkin_lean import scan_lean_sources
        sources.extend(scan_lean_sources(_TM81_CONFIG_DIR, TM81GenericTestSource, _TM81_STEPS_JSON))
        # Suite OTA ringkas -- JSON-nya diperkecil jadi cuma fw_version +
        # _dialog (masih dibaca/ditulis tombol "OTA Settings" di GUI apa
        # adanya), daftar/urutan step-nya dari .feature. Lihat
        # loaders/gherkin_lean.py:scan_lean_sources(ota_only=True).
        sources.extend(scan_lean_sources(_TM81_CONFIG_DIR, TM81OtaTestSource, _TM81_STEPS_JSON,
                                          ota_only=True))
    except Exception as e:
        _log.warning("Gagal load lean TM81 sources: %s", e)

    return sources


_tm81_extra_sources: list[JsonTestSource] = _scan_tm81_sources()


def reload_tm81_extra_sources() -> None:
    """Re-scan folder config. Panggil jika JSON baru ditambah saat app berjalan."""
    global _tm81_extra_sources
    _tm81_extra_sources = _scan_tm81_sources()


def get_tm81_extra_sources() -> list[JsonTestSource]:
    """Return semua TM81 sources yang auto-discovered."""
    return list(_tm81_extra_sources)


# ---------------------------------------------------------------------------
# Public API — thin wrappers untuk backward compatibility
# ---------------------------------------------------------------------------

def _get_source_by_prefix(prefix: str) -> "JsonTestSource | None":
    for src in _tm81_extra_sources:
        if src.prefix == prefix:
            return src
    return None


def load_tm81_tests() -> list:
    """Load semua test dari source dengan prefix 'tm81' (tm81_test.json)."""
    src = _get_source_by_prefix("tm81")
    return src.load_all() if src else []


def tm81_module_names() -> list:
    """Return module names dari source prefix 'tm81'."""
    src = _get_source_by_prefix("tm81")
    return src.module_names() if src else []


def tm81_label() -> str:
    """Return label dari source prefix 'tm81'."""
    src = _get_source_by_prefix("tm81")
    return src.label() if src else "TM81"


def load_tm81_test(entry_name: str):
    """Load satu entry dari source prefix 'tm81' (dipakai test_loader.load_test)."""
    src = _get_source_by_prefix("tm81")
    if src is None:
        raise KeyError(
            f"TM81 source tidak ditemukan — pastikan tm81_test.json ada "
            f"di {_TM81_CONFIG_DIR} dengan field \"prefix\": \"tm81\""
        )
    return src.load_one(entry_name)
