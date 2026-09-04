"""
loaders/bexa.py — BEXA test source (via Bluetooth SPP).
"""

import logging
import os

from test_modules import build_test_item
from loaders.base import JsonTestSource, _ROOT
from validation_rules import apply_expect_check

_log      = logging.getLogger(__name__)
_BEXA_JSON = os.path.join(_ROOT, "commands", "bexa", "config", "bexa_test.json")


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


def load_bexa_tests() -> list:
    return _bexa_source.load_all()


def bexa_module_names() -> list[str]:
    return _bexa_source.module_names()


def bexa_label() -> str:
    return _bexa_source.label()


def load_bexa_test(entry_name: str):
    """Load satu BEXA test entry dari bexa_test.json."""
    return _bexa_source.load_one(entry_name)
