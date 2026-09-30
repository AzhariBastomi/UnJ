"""
loaders/voltage.py — Voltage test loader.

Daftar titik ukur tegangan dibaca dari commands/voltage/config/voltage.feature
(urutan & titik mana yang aktif) + commands/voltage/config/_steps.json
(definisi tiap titik: label/command/description) -- format sama seperti
mode lean di device lain (lihat lib/loaders/gherkin_lean.py), tapi ditulis
manual di sini (bukan lewat scan_lean_sources/make_lean_source_class) karena
modelnya beda: TIAP titik ukur jadi source/baris Add Test SENDIRI-SENDIRI
(bukan satu suite dengan banyak step yang digabung jadi satu TestItem list).

Satu titik ukur = satu VoltageTestSource = satu ManualTest, sama seperti
sebelumnya -- yang berubah cuma sumber datanya (dulu 1 file JSON per titik,
sekarang 1 baris di voltage.feature + definisi di _steps.json).
"""

import logging
import os

from test_modules import ManualTest
from loaders.base import JsonTestSource, _ROOT, read_steps_library

_log        = logging.getLogger(__name__)
_VOLT_DIR   = os.path.join(_ROOT, "commands", "voltage", "config")
_STEPS_JSON = os.path.join(_VOLT_DIR, "_steps.json")
_FEATURE    = os.path.join(_VOLT_DIR, "voltage.feature")


class VoltageTestSource(JsonTestSource):
    """Satu titik ukur tegangan = satu test source dengan satu ManualTest."""

    prefix       = "voltage"
    entity_label = "Voltage test"

    def __init__(self, name: str, entry: dict):
        # json_path di sini cuma dipakai buat pesan error/referensi -- isi
        # sebenarnya dari _steps.json + voltage.feature, bukan file JSON
        # per-titik lagi.
        self.json_path = _FEATURE
        self._name     = name
        self._label    = entry.get("label", name)
        self._command  = entry.get("command", f"VOLT_{name.upper()}")
        self._desc     = entry.get("description", f"Cek tegangan {self._label}")

    # --- overrides ---

    def label(self) -> str:
        return self._label

    def module_names(self) -> list[str]:
        return [f"voltage:{self._name}"]

    def load_all(self) -> list:
        return [self._build_item()]

    def load_one(self, entry_name: str) -> ManualTest:
        if entry_name != self._name:
            raise KeyError(f"Voltage '{entry_name}' tidak ditemukan di voltage.feature")
        return self._build_item()

    def make_item(self, entry: dict) -> ManualTest:
        return self._build_item()

    def _build_item(self) -> ManualTest:
        return ManualTest(
            title=f"Voltage {self._label}",
            command=self._command,
            description=self._desc,
            run_fn=None,
        )


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

def _scan_voltage_sources() -> list[VoltageTestSource]:
    """Baca voltage.feature (daftar titik ukur aktif + urutan) + _steps.json
    (definisi tiap titik), bikin satu VoltageTestSource per baris."""
    sources = []

    library = read_steps_library(_STEPS_JSON)
    if not library:
        _log.warning("_steps.json voltage kosong/tidak ada: %s", _STEPS_JSON)
        return sources

    try:
        from loaders.gherkin_common import parse_feature_steps_with_tables
        steps = parse_feature_steps_with_tables(_FEATURE)
    except Exception as exc:
        _log.warning("Gagal baca voltage.feature: %s", exc)
        return sources

    by_key = {k.lower(): k for k in library}
    for sentence, _table in steps:
        needle = sentence.strip().lower()
        key = by_key.get(needle)
        if key is None:
            _log.warning(
                "Voltage: baris '%s' di voltage.feature tidak match nama "
                "manapun di _steps.json -- dilewati", sentence
            )
            continue
        try:
            sources.append(VoltageTestSource(key, library[key]))
        except Exception as exc:
            _log.warning("Gagal load voltage entry %s: %s", key, exc)

    return sources


_voltage_sources: list[VoltageTestSource] = _scan_voltage_sources()


def reload_voltage_sources() -> None:
    """Re-scan voltage.feature/_steps.json. Panggil jika diubah saat app berjalan."""
    global _voltage_sources
    _voltage_sources = _scan_voltage_sources()


def get_voltage_sources() -> list[VoltageTestSource]:
    return list(_voltage_sources)


# ---------------------------------------------------------------------------
# Public API — kompatibel dengan __init__.py & test_loader.py
# ---------------------------------------------------------------------------

def load_voltage_tests() -> list:
    return [item for src in _voltage_sources for item in src.load_all()]


def voltage_module_names() -> list[str]:
    return [name for src in _voltage_sources for name in src.module_names()]


def _load_voltage_by_name(entry_name: str) -> ManualTest:
    for src in _voltage_sources:
        if src._name == entry_name:
            return src.load_one(entry_name)
    raise KeyError(f"Voltage entry '{entry_name}' tidak ditemukan di {_FEATURE}")
