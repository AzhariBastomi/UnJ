"""
loaders/base.py — Base class JsonTestSource (Template Method Pattern).

TM81, BEXA, dan semua source lain berbagi logika: baca JSON, filter entry
disabled, resolve command_class dinamis, derive label & module_names.
Subclass hanya perlu override make_item(entry).
"""

import importlib
import json
import logging
import os
import sys

_log  = logging.getLogger(__name__)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class JsonTestSource:
    json_path:    str = ""      # path file JSON — di-set di subclass atau __init__
    prefix:       str = ""      # dipakai di module_names(), mis. "tm81"
    entity_label: str = "Test"  # dipakai di pesan error

    def read_json(self) -> dict:
        try:
            with open(self.json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def is_enabled(self, entry: dict) -> bool:
        """Entry aktif jika 'name' ada dan 'disabled' != true."""
        return "name" in entry and not entry.get("disabled", False)

    def label(self) -> str:
        cfg = self.read_json()
        if cfg.get("label"):
            return cfg["label"]
        stem = os.path.splitext(os.path.basename(self.json_path))[0]
        return stem.replace("_", " ").title()

    def module_names(self) -> list[str]:
        cfg = self.read_json()
        return [
            f"{self.prefix}:{e['name']}"
            for e in cfg.get("tests", [])
            if self.is_enabled(e)
        ]

    def load_all(self) -> list:
        cfg = self.read_json()
        return [self.make_item(e) for e in cfg.get("tests", []) if self.is_enabled(e)]

    def load_one(self, entry_name: str):
        cfg       = self.read_json()
        json_file = os.path.basename(self.json_path)
        for e in cfg.get("tests", []):
            if e.get("name") == entry_name:
                if not self.is_enabled(e):
                    raise KeyError(
                        f"{self.entity_label} '{entry_name}' di-disabled di {json_file}"
                    )
                return self.make_item(e)
        raise KeyError(
            f"{self.entity_label} '{entry_name}' tidak ditemukan di {json_file}"
        )

    @staticmethod
    def resolve_command_class(class_path: str):
        """Import command_class secara dinamis. Return (cls, error_message)."""
        if not class_path:
            return None, ""
        try:
            if _ROOT not in sys.path:
                sys.path.insert(0, _ROOT)
            mod_path, cls_name = class_path.rsplit(".", 1)
            mod = importlib.import_module(mod_path)
            return getattr(mod, cls_name), ""
        except Exception as e:
            return None, str(e)

    def make_item(self, entry: dict):
        """Override di subclass: bangun satu TestItem dari satu entry JSON."""
        raise NotImplementedError
