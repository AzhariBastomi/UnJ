"""
lib/task_store.py — Persistensi tasks.json.

Diambil dari main.py.App yang tadinya menangani baca/tulis tasks.json sekaligus
jadi bagian dari class App (God Object). TaskStore hanya tahu soal file I/O dan
format versinya — tidak tahu apa-apa soal Tkinter atau TestItem. App yang
menerjemahkan dict hasil load() jadi state UI (test list, project, keepalive, dst).
"""

import json
import logging
import os

log = logging.getLogger("main")


class TaskStore:
    """Baca/tulis tasks.json di root project."""

    VERSION = 2

    def __init__(self, path: str = None):
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = path or os.path.join(_root, "tasks.json")

    def load(self) -> dict:
        """Return dict data tasks.json, atau {} kalau file tidak ada / rusak /
        versinya lebih baru dari yang didukung aplikasi ini.

        Format lama (list mentah nama test) dinormalisasi jadi {"tests": [...]}.
        """
        if not os.path.isfile(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning("Gagal load tasks.json: %s", e)
            return {}

        if isinstance(data, list):
            return {"tests": data}

        ver = data.get("version", 1)
        if ver > self.VERSION:
            log.warning(
                "tasks.json version %d lebih baru dari yang didukung (%d), skip.",
                ver, self.VERSION,
            )
            return {}
        return data

    def save(self, data: dict) -> None:
        """Simpan dict data (tanpa key 'version' — otomatis ditambahkan)."""
        try:
            payload = {"version": self.VERSION, **data}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            log.warning("Gagal simpan tasks.json: %s", e)
