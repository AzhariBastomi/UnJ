"""
loaders/bexa.py — BEXA test source (via Bluetooth SPP).
"""

import logging
import os

from test_modules import build_test_item
from loaders.base import JsonTestSource, _ROOT
from validation_rules import apply_expect_check

_log       = logging.getLogger(__name__)
_BEXA_CONFIG_DIR = os.path.join(_ROOT, "commands", "bexa", "config")
_BEXA_JSON       = os.path.join(_BEXA_CONFIG_DIR, "bexa_test.json")
_BEXA_STEPS_JSON = os.path.join(_BEXA_CONFIG_DIR, "_steps.json")


class BexaTestSource(JsonTestSource):
    """Test dari bexa_test.json — murni command_class + run_fn, tanpa commissioning."""

    json_path    = _BEXA_JSON
    prefix       = "bexa"
    entity_label = "BEXA test"

    def make_item(self, entry: dict):
        name     = entry.get("name", "unknown")
        label    = entry.get("label", name)
        desc     = entry.get("description", "")
        cls_path = entry.get("command_class", "")
        ttype    = entry.get("type", "auto").lower()

        _cmd_cls, _load_err = self.resolve_command_class(cls_path)
        _expect = entry.get("expect")

        def _run_fn():
            if _cmd_cls is None:
                return f"NG:{_load_err or 'command_class tidak diset'}"
            try:
                _log.info("[BEXA] %s", label)
                result = _cmd_cls().execute()
                if _expect:
                    result = apply_expect_check(result, _expect)
                return result
            except Exception as e:
                _log.exception("[BEXA] %s exception:", label)
                return f"NG:{e}"

        kw = dict(title=label, command=f"BEXA_{name.upper()}",
                  description=desc, run_fn=_run_fn,
                  no_retry=entry.get("no_retry", False))
        return build_test_item(ttype, **kw)


_bexa_source = BexaTestSource()


def _resolve_active_bexa_source():
    """Tiga kemungkinan sumber BEXA test, dicek berurutan:

    1. bexa_test.json TIDAK ADA tapi features/bexa_test.feature ADA -- mode
       "ringkas" (lean): isi tiap step diambil dari _steps.json library,
       urutan/pilihan step murni dari .feature. Ini yang dipakai kalau
       bexa_test.json sudah dihapus.
    2. bexa_test.json ADA dan features/bexa_test.feature ADA -- mode
       "replace in place": isi step tetap dari bexa_test.json (expect, dll),
       .feature cuma override urutan/seleksi. Lihat loaders/gherkin_common.py.
    3. Kalau tidak ada .feature sama sekali -- fallback ke JSON biasa.
    """
    # Mode lean: .feature-nya di FOLDER CONFIG langsung (bukan di features/,
    # itu lokasi mode replace-in-place) -- lihat loaders/gherkin_lean.py.
    lean_feature_path = os.path.join(_BEXA_CONFIG_DIR, "bexa_test.feature")

    if os.path.isfile(lean_feature_path) and not os.path.isfile(_BEXA_JSON):
        try:
            from loaders.gherkin_lean import make_lean_source_class
            lean_cls = make_lean_source_class(BexaTestSource, _BEXA_STEPS_JSON)
            return lean_cls(lean_feature_path)
        except Exception as e:
            _log.warning("Gagal load lean BEXA source: %s", e)

    try:
        from loaders.gherkin_common import wrap_if_feature_exists
        g = wrap_if_feature_exists(_bexa_source)
        return g if g is not None else _bexa_source
    except Exception as e:
        _log.warning("Gagal load Gherkin BEXA source: %s", e)
        return _bexa_source


_active_bexa_source = _resolve_active_bexa_source()


def load_bexa_tests() -> list:
    return _active_bexa_source.load_all()


def bexa_module_names() -> list[str]:
    return _active_bexa_source.module_names()


def bexa_label() -> str:
    return _active_bexa_source.label()


def load_bexa_test(entry_name: str):
    """Load satu BEXA test entry dari bexa_test.json."""
    return _active_bexa_source.load_one(entry_name)
