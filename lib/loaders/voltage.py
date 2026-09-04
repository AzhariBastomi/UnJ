"""
loaders/voltage.py — Voltage test loader.

Auto-discover dari commands/voltage/config/*.json.
Satu file JSON = satu VoltageTestSource = satu ManualTest.
Pola sama dengan TM81: setiap source independent, bukan digabung jadi satu batch.
"""

import logging
import os

from test_modules import ManualTest
from loaders.base import JsonTestSource, _ROOT

_log      = logging.getLogger(__name__)
_VOLT_DIR = os.path.join(_ROOT, "commands", "voltage", "config")


class VoltageTestSource(JsonTestSource):
    """Satu voltage JSON file = satu test source dengan satu ManualTest."""

    prefix       = "voltage"
    entity_label = "Voltage test"

    def __init__(self, json_path: str):
        self.json_path = json_path
        data           = self.read_json()
        stem           = os.path.splitext(os.path.basename(json_path))[0]
        self._name     = data.get("name", stem)
        self._label    = data.get("label", self._name)
        self._command  = data.get("command", f"VOLT_{self._name.upper()}")
        self._desc     = data.get("description", f"Cek tegangan {self._label}")

    # --- overrides ---

    def label(self) -> str:
        return self._label

    def module_names(self) -> list[str]:
        return [f"voltage:{self._name}"]

    def load_all(self) -> list:
        return [self._build_item()]

    def load_one(self, entry_name: str) -> ManualTest:
        if entry_name != self._name:
            fname = os.path.basename(self.json_path)
            raise KeyError(f"Voltage '{entry_name}' tidak ditemukan di {fname}")
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
    """Scan commands/voltage/config/, buat satu VoltageTestSource per *.json."""
    sources = []
    try:
        for fname in sorted(os.listdir(_VOLT_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(_VOLT_DIR, fname)
            try:
                sources.append(VoltageTestSource(path))
            except Exception as exc:
                _log.warning("Gagal load voltage config %s: %s", fname, exc)
    except FileNotFoundError:
        _log.warning("Folder voltage config tidak ditemukan: %s", _VOLT_DIR)
    return sources


_voltage_sources: list[VoltageTestSource] = _scan_voltage_sources()


def reload_voltage_sources() -> None:
    """Re-scan folder. Panggil jika JSON baru ditambah saat app berjalan."""
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
    raise KeyError(f"Voltage entry '{entry_name}' tidak ditemukan di {_VOLT_DIR}")
