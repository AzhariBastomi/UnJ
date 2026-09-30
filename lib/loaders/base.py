"""
loaders/base.py — Base class JsonTestSource (Template Method Pattern).

TM81, BEXA, dan semua source lain berbagi logika: baca JSON, filter entry
disabled, resolve command_class dinamis, derive label & module_names.
Subclass hanya perlu override make_item(entry).

Dua format suite didukung, keduanya menghasilkan list entry yang sama:

  1. "tests"  — array entry lengkap (format lama, tetap jalan apa adanya).

  2. "steps"  — array ringkas yang merujuk step library (steps_json).
                Elemen boleh berupa:
                  "nama_step"                     -> pakai definisi library apa adanya
                  {"use": "nama_step", ...}       -> definisi library + override
                  {"name": ..., "command_class":} -> entry inline, tidak lewat library

                Override adalah shallow merge di level field: field yang
                disebut menimpa punya library, sisanya diwarisi. Berguna untuk
                description, expect, post_wait_s, post_popup, dst.
                Set sebuah field ke null untuk MEMBUANG bawaan library.
                Sertakan "name" untuk memakai varian library tanpa mengubah
                nama step yang dipakai tasks.json, mis.
                  {"use": "bl_goto_app_ota", "name": "bl_goto_app"}

Kalau kedua field ada, "steps" yang dipakai.
"""

import importlib
import json
import logging
import os
import sys

_log  = logging.getLogger(__name__)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Cache step library per path: {path: (mtime, dict)}. Dibaca ulang hanya
# saat file berubah, sama polanya dengan cache commissioning.json.
_steps_cache: dict = {}


def read_steps_library(path: str) -> dict:
    """Baca step library JSON dengan cache per mtime. Return {} bila tidak ada."""
    if not path:
        return {}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = _steps_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        steps = data.get("steps", data)
        steps = {k: v for k, v in steps.items() if not k.startswith("_")}
    except Exception as e:
        _log.warning("Gagal baca step library %s: %s", os.path.basename(path), e)
        steps = {}
    _steps_cache[path] = (mtime, steps)
    return steps


class JsonTestSource:
    json_path:    str = ""      # path file JSON — di-set di subclass atau __init__
    prefix:       str = ""      # dipakai di module_names(), mis. "tm81"
    entity_label: str = "Test"  # dipakai di pesan error
    steps_json:   str = ""      # path step library; kosong = format "steps" tidak dipakai

    def entries(self, cfg: dict = None) -> list[dict]:
        """Return list entry lengkap dari suite, apapun format JSON-nya.

        Format "steps" di-resolve lewat step library; format "tests" lama
        dikembalikan apa adanya. Ini satu-satunya pintu masuk entry, jadi
        module_names/load_all/load_one otomatis mendukung keduanya.
        """
        if cfg is None:
            cfg = self.read_json()
        raw = cfg.get("steps")
        if raw is None:
            return cfg.get("tests", [])
        library = read_steps_library(self.steps_json)
        return [self._resolve_step(s, library) for s in raw]

    def _resolve_step(self, step, library: dict) -> dict:
        """Resolve satu elemen "steps" jadi entry lengkap."""
        # Bentuk 1: string biasa -> ambil apa adanya dari library
        if isinstance(step, str):
            name, override = step, {}
        elif isinstance(step, dict):
            name = step.get("use")
            # Bentuk 3: entry inline (tanpa "use") -> lewati library
            if not name:
                return dict(step)
            override = {k: v for k, v in step.items() if k != "use"}
        else:
            return self._unknown_step(str(step), "elemen steps harus string atau objek")

        base = library.get(name)
        if base is None:
            return self._unknown_step(name, "tidak ada di step library")

        entry = dict(base)
        entry.update(override)
        # name default = kunci library, tapi suite boleh menimpanya supaya
        # bisa memakai varian library tanpa mengubah nama step di tasks.json.
        entry["name"] = override.get("name") or name
        # null = buang field bawaan library
        return {k: v for k, v in entry.items() if v is not None}

    def _unknown_step(self, name: str, reason: str) -> dict:
        """Entry pengganti untuk step yang gagal di-resolve.

        Sengaja tetap dikembalikan (bukan di-skip) supaya kesalahan ketik
        muncul sebagai row NG di UI, bukan step yang diam-diam hilang.
        """
        lib_file = os.path.basename(self.steps_json) or "step library"
        _log.warning("Step '%s' %s (%s)", name, reason, lib_file)
        return {
            "name":          name,
            "label":         f"{name} (step tidak dikenal)",
            "command_class": "",
            "description":   f"Step '{name}' {reason} — periksa {lib_file}.",
        }

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
            for e in self.entries(cfg)
            if self.is_enabled(e)
        ]

    def load_all(self) -> list:
        cfg = self.read_json()
        return [self.make_item(e) for e in self.entries(cfg) if self.is_enabled(e)]

    def load_one(self, entry_name: str):
        cfg       = self.read_json()
        json_file = os.path.basename(self.json_path)
        for e in self.entries(cfg):
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
