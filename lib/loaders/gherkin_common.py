"""
loaders/gherkin_common.py -- Utilitas generik untuk bikin varian "Gherkin"
dari JsonTestSource MANA PUN (TM81, BEXA, Flash, dst): urutan + seleksi step
dibaca dari file .feature, isi tiap step (command_class, params, validate,
expect) tetap dari resolusi JSON asli -- jadi perilaku eksekusi 100% sama
dengan source JSON biasa, cuma urutan/pilihannya yang beda. Kalimat di
.feature dicocokkan LANGSUNG ke "name"/"label" tiap entry hasil resolve
JSON -- tidak perlu file map terpisah kecuali ada kasus lama yang masih
punya _map_<stem>.json (dipakai sbg fallback saja, lihat _load_step_map()).

Dipakai lewat wrap_if_feature_exists(source) -- lihat pemanggilannya di
_scan_tm81_sources() (loaders/tm81.py), _scan_flash_sources() (loaders/flash.py),
dan get_bexa_extra_sources() (loaders/bexa.py).

Tidak spesifik ke satu device: bekerja untuk source class apa pun yang
mewarisi JsonTestSource (lihat loaders/base.py), termasuk yang __init__-nya
menerima json_path (TM81*, FlashTestSource) maupun yang json_path-nya
konstanta class-level tanpa __init__ sendiri (BexaTestSource).
"""

import json
import logging
import os
import re

_log = logging.getLogger(__name__)

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_STEP_KW      = ("Given", "When", "Then", "And", "But", r"\*")
_STEP_LINE_RE = re.compile(r"^\s*(?:" + "|".join(_STEP_KW) + r")\s+(.+?)\s*$")


def feature_path_for(json_path: str) -> "str | None":
    """Return path <stem>.feature di FOLDER YANG SAMA dengan json_path kalau
    ada, else None. Sengaja satu folder dengan JSON-nya (bukan folder
    features/ terpusat) supaya semua file satu suite (JSON, .feature,
    _map_<stem>.json) ngumpul di folder config device masing-masing."""
    stem = os.path.splitext(os.path.basename(json_path))[0]
    path = os.path.join(os.path.dirname(json_path), f"{stem}.feature")
    return path if os.path.isfile(path) else None


def _map_path_for(json_path: str) -> str:
    stem = os.path.splitext(os.path.basename(json_path))[0]
    return os.path.join(os.path.dirname(json_path), f"_map_{stem}.json")


def _parse_feature_sentences(feature_path: str) -> list:
    """Baca .feature, kembalikan list kalimat step sesuai urutan baris.

    Baris kosong, comment ("#"), dan header (Feature:/Scenario:/dst) dilewati
    otomatis -- jadi non-programmer bisa comment-out atau hapus baris step
    tanpa bikin parser ini error.
    """
    sentences = []
    with open(feature_path, encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith(("Feature:", "Scenario:", "Scenario Outline:",
                                     "Background:", "Examples:")):
                continue
            m = _STEP_LINE_RE.match(raw_line.rstrip("\n"))
            if m:
                sentences.append(m.group(1).strip())
    return sentences


def parse_feature_steps_with_tables(feature_path: str) -> list:
    """Sama seperti _parse_feature_sentences(), tapi juga tangkap Data Table
    Gherkin (baris "| key | value |") yang nempel langsung di bawah satu
    step -- dipakai buat override "expect" inline tanpa perlu JSON suite
    terpisah (mirip variable/argument di keyword Robot Framework).

    Return list[(kalimat, dict_table_atau_None)].
    """
    steps = []
    with open(feature_path, encoding="utf-8") as f:
        raw_lines = f.readlines()

    i, n = 0, len(raw_lines)
    while i < n:
        raw_line = raw_lines[i]
        stripped = raw_line.strip()
        i += 1
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("Feature:", "Scenario:", "Scenario Outline:",
                                 "Background:", "Examples:")):
            continue
        m = _STEP_LINE_RE.match(raw_line.rstrip(chr(10)))
        if not m:
            continue
        sentence = m.group(1).strip()

        table = {}
        while i < n:
            nxt = raw_lines[i].strip()
            if nxt.startswith("|") and nxt.endswith("|") and len(nxt) > 1:
                cells = [c.strip() for c in nxt.strip("|").split("|")]
                if len(cells) >= 2 and cells[0]:
                    table[cells[0]] = cells[1]
                i += 1
            else:
                break
        steps.append((sentence, table or None))
    return steps


def _load_step_map(json_path: str) -> dict:
    path = _map_path_for(json_path)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_gherkin_class(base_cls, feature_path):
    """Bikin subclass Gherkin dari base_cls (JsonTestSource apa pun): urutan
    step di entries() dibaca dari .feature (isi tiap step tetap dari
    resolusi base_cls asli). Prefix & label TIDAK diubah -- source ini
    dimaksudkan untuk MENGGANTIKAN source JSON di posisi yang sama,
    bukan jadi baris terpisah.

    __init__ dipanggil lewat base_cls langsung (bukan super()) supaya cocok
    baik base_cls punya __init__(self, json_path) sendiri (TM81*, Flash)
    ataupun tidak -- json_path-nya konstanta class-level (BEXA).
    """

    def __init__(self, json_path, _feature_path=feature_path):
        if base_cls.__init__ is not object.__init__:
            base_cls.__init__(self, json_path)
        else:
            self.json_path = json_path
        self.feature_path = _feature_path
        # Sengaja TIDAK menyuffix prefix/label -- source ini MENGGANTIKAN
        # source JSON biasa di daftar Add Test (bukan baris tambahan
        # terpisah), jadi harus tetap kompatibel dengan kode lain yang
        # bergantung pada prefix asli (project.py, test_loader.load_test(),
        # daftar test tersimpan di tasks.json).

    def label(self):
        return base_cls.label(self)

    def entries(self, cfg=None, _feature_path=feature_path):
        original = base_cls.entries(self, cfg)
        by_name  = {e.get("name", ""): e for e in original}
        by_label: dict = {}
        for e in original:
            lbl = str(e.get("label", "")).strip().lower()
            if lbl:
                by_label.setdefault(lbl, []).append(e)

        # File map (_map_<stem>.json) cuma fallback legacy -- entry hasil
        # resolve base_cls SUDAH punya "name"/"label" sendiri, jadi kalimat
        # di .feature dicocokkan LANGSUNG ke situ dulu (sama seperti mode
        # lean, lihat gherkin_lean.py), tanpa perlu file map terpisah.
        step_map = None

        out = []
        for sentence in _parse_feature_sentences(_feature_path):
            entry = by_name.get(sentence)
            if entry is None:
                hits = by_label.get(sentence.strip().lower(), [])
                if len(hits) == 1:
                    entry = hits[0]
                elif len(hits) > 1:
                    out.append(self._unknown_step(
                        sentence,
                        f'label "{sentence}" dipakai {len(hits)} entry berbeda -- '
                        f'tulis nama entry-nya langsung supaya jelas'
                    ))
                    continue
            if entry is None:
                if step_map is None:
                    step_map = _load_step_map(self.json_path)
                key   = step_map.get(sentence)
                entry = by_name.get(key) if key else None
            if entry is None:
                out.append(self._unknown_step(
                    sentence,
                    f"kalimat di {os.path.basename(_feature_path)} tidak match "
                    f"ke step manapun (nama/label) -- cek ejaan, atau regenerasi "
                    f"lewat tools/json_to_gherkin.py kalau JSON-nya baru diubah"
                ))
                continue
            out.append(entry)
        return out

    return type(f"Gherkin{base_cls.__name__}", (base_cls,), {
        "__init__": __init__,
        "label":    label,
        "entries":  entries,
    })


def wrap_if_feature_exists(source):
    """Kalau ada features/<stem>.feature yang cocok utk source JSON ini,
    return source Gherkin tambahan (untuk didaftarkan sebagai baris terpisah
    di Add Test). Return None kalau tidak ada .feature -- suite itu tidak
    kepengaruh sama sekali."""
    feature_path = feature_path_for(source.json_path)
    if not feature_path:
        return None
    try:
        gherkin_cls = _build_gherkin_class(type(source), feature_path)
        return gherkin_cls(source.json_path)
    except Exception as e:
        _log.warning("Gagal bikin Gherkin source utk %s: %s", source.json_path, e)
        return None
