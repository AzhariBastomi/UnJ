"""
loaders/gherkin_lean.py -- Suite "ringkas": SATU file .feature langsung di
folder config device-nya (commands/tm81/config/, commands/bexa/config/),
TANPA JSON suite terpisah dan TANPA file map -- taruh di folder config
device-nya sendiri (commands/tm81/config/, commands/bexa/config/, dst).

Ini buat kasus paling umum: mau nambah suite baru yang isinya cuma
kombinasi/urutan step yang SUDAH ADA di step library (_steps.json), dengan
override yang didukung ditulis langsung di .feature (lihat di bawah).

Cara pakai -- taruh file <nama>.feature langsung di folder config device
terkait, tiap baris pakai LABEL atau NAMA step dari _steps.json:

    Feature: TM81 Join 3

      Scenario: TM81 Join 3
        Given user_reset_config: Reset konfigurasi user ke default
        Then user_get_config
          | Activation | Deactivated |
        And Set RTC
          | tunggu | 1.5 |
        And sensor_calibration

Konvensi yang didukung per baris step:
  - "nama_step: teks deskripsi"  -> override "description"
  - Data Table "| key | value |" di bawahnya:
      - key "tunggu"/"wait"/"delay"/"post_wait_s"  -> override "post_wait_s" (detik)
      - key berawalan "!" (mis. "!counter_res")     -> masuk ke "validate"
      - key lainnya                                 -> masuk ke "expect"

Simpan file -> otomatis muncul di Add Test, TIDAK PERLU generate apa pun.
Kalau suite JSON dengan nama sama juga ada di folder yang sama, .feature ini
diabaikan (suite JSON menang -- supaya tidak konflik dengan jalur biasa).

Batas yang BELUM didukung lean (masih butuh suite JSON): "params" custom,
varian step ("use" + "name" beda), dan suite OTA TM81 (field
fw_version/_dialog + class TM81OtaTestSource -- lihat gherkin_lean_ota.py).
"""
import json
import logging
import os

from loaders.base import read_steps_library
from loaders.gherkin_common import parse_feature_steps_with_tables

_log = logging.getLogger(__name__)


def _resolve_table(entry, sentence, table, unknown_step_fn):
    """Pecah satu Data Table jadi post_wait_s / validate / expect, lalu
    tempelkan ke entry. Return True kalau berhasil (entry siap dipakai),
    False kalau ada error (sudah ditambahkan sbg unknown_step ke caller)."""
    if not table:
        return True

    wait_keys  = {"tunggu", "tunggu (detik)", "wait", "wait_s", "delay", "post_wait_s"}
    label_keys = {"label", "judul"}
    wait_val, label_val, expect_table, validate_table = None, None, {}, {}
    for tk, tv in table.items():
        tk_stripped = tk.strip()
        if tk_stripped.lower() in wait_keys:
            wait_val = tv
        elif tk_stripped.lower() in label_keys:
            label_val = tv
        elif tk_stripped.startswith("!"):
            validate_table[tk_stripped[1:].strip()] = tv
        else:
            expect_table[tk_stripped] = tv

    if wait_val is not None:
        try:
            entry["post_wait_s"] = float(str(wait_val).replace(",", "."))
        except ValueError:
            unknown_step_fn(sentence, f'nilai tunggu "{wait_val}" bukan angka detik yang valid')
            return False

    if label_val is not None:
        entry["label"] = str(label_val).strip()

    if expect_table:
        entry["expect"] = expect_table

    if validate_table:
        parsed_validate = {}
        for vk, vv in validate_table.items():
            vv_stripped = str(vv).strip()
            if vv_stripped.lower() in ("nonzero", "nonzero_hex"):
                parsed_validate[vk] = vv_stripped.lower()
            else:
                try:
                    parsed_validate[vk] = int(vv_stripped)
                except ValueError:
                    unknown_step_fn(
                        sentence,
                        f'nilai validate "{vv}" untuk "{vk}" tidak dikenal -- '
                        f'pakai angka, "nonzero", atau "nonzero_hex"'
                    )
                    return False
        entry["validate"] = parsed_validate

    return True


def _read_feature_label(path: str) -> "str | None":
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("Feature:"):
                    return s[len("Feature:"):].strip()
    except Exception:
        pass
    return None


def _read_feature_prefix(path: str) -> "str | None":
    """Baca comment "# prefix: xxx" di header .feature (kalau ada) -- dipakai
    saat suite JSON sumbernya dulu punya field "prefix" custom (beda dari
    nama file), mis. tm81_test.json -> "prefix": "tm81". Tanpa ini, module
    name (task persistence, dispatch di test_loader.py, project.py) akan
    berubah begitu suite pindah ke mode ringkas (JSON dihapus)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if not s.startswith("#"):
                    break  # header comment selesai
                if s.lower().startswith("# prefix:"):
                    val = s.split(":", 1)[1].strip()
                    return val or None
    except Exception:
        pass
    return None


def make_lean_source_class(base_cls, steps_json_path: str, settings_json_path: "str | None" = None):
    """Bikin subclass lean dari base_cls (JsonTestSource apa pun yang punya
    make_item() siap pakai -- TM81GenericTestSource, BexaTestSource,
    TM81OtaTestSource, dst). entries() di-resolve dari .feature +
    steps_json_path, TIDAK dari suite JSON. __init__ dipanggil lewat
    base_cls langsung (bukan super()) supaya cocok baik base_cls minta
    json_path di __init__ atau tidak.

    settings_json_path (opsional): JSON KECIL yang TIDAK berisi daftar step
    ("steps"/"tests"), cuma field pengaturan lain yang masih dibaca base_cls
    lewat read_json()/self._cfg -- misalnya "fw_version" + "_dialog" di
    TM81OtaTestSource (dipakai tombol "OTA Settings" GUI, lihat
    ui/dialogs/json_field_dialog.py). Kalau di-isi, read_json() baca file
    itu apa adanya (bukan {}), tapi entries() TETAP dari .feature seperti
    biasa -- jadi daftar/urutan step tetap 100% dari .feature.
    """

    def __init__(self, feature_path: str):
        stem = os.path.splitext(os.path.basename(feature_path))[0]
        if base_cls.__init__ is not object.__init__:
            try:
                base_cls.__init__(self, feature_path)
            except Exception:
                pass
        self.feature_path = feature_path
        self.json_path    = settings_json_path or feature_path
        self.prefix        = _read_feature_prefix(feature_path) or stem
        self.entity_label   = f"{stem.replace('_', ' ').title()} test (ringkas)"
        self._label         = _read_feature_label(feature_path) or stem.replace("_", " ").title()

    def label(self) -> str:
        return self._label

    def read_json(self) -> dict:
        if not settings_json_path:
            return {}
        try:
            with open(settings_json_path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("label"):
                self._label = data["label"]
            return data
        except Exception as e:
            _log.warning("Gagal baca settings JSON %s: %s", settings_json_path, e)
            return {}

    def entries(self, cfg: dict = None) -> list:
        library  = read_steps_library(steps_json_path)
        by_key   = {k.lower(): (k, v) for k, v in library.items()}
        by_label: dict = {}
        for k, v in library.items():
            lk = v.get("label", "").strip().lower()
            if lk:
                by_label.setdefault(lk, []).append((k, v))

        out = []

        def unknown(sentence, reason):
            out.append(self._unknown_step(sentence, reason))

        for sentence, table in parse_feature_steps_with_tables(self.feature_path):
            if ":" in sentence:
                step_ref, custom_desc = sentence.split(":", 1)
                step_ref, custom_desc = step_ref.strip(), custom_desc.strip()
            else:
                step_ref, custom_desc = sentence, None

            # Konvensi "nama_step_variant => nama_baru" -- setara "use"+"name"
            # di suite JSON lama: pakai definisi step "nama_step_variant" dari
            # step library, tapi entry hasil akhirnya dipakai dengan nama
            # "nama_baru". Berguna kalau satu step di library punya beberapa
            # varian (mis. "write_fw_v1"/"write_fw_v2") yang semuanya perlu
            # tampil dengan nama step yang SAMA ("write_fw") supaya kode lain
            # yang cek nama step persis (mis. TM81OtaTestSource.make_item())
            # tetap kena.
            rename_to = None
            if "=>" in step_ref:
                step_ref, rename_to = step_ref.split("=>", 1)
                step_ref, rename_to = step_ref.strip(), rename_to.strip()

            needle = step_ref.lower()
            key_hit    = by_key.get(needle)
            label_hits = by_label.get(needle, [])

            if key_hit is not None:
                hit = key_hit
            elif len(label_hits) == 1:
                hit = label_hits[0]
            elif len(label_hits) > 1:
                names = ", ".join(k for k, _ in label_hits)
                unknown(sentence, f'label "{step_ref}" dipakai {len(label_hits)} step '
                                   f'berbeda ({names}) -- tulis nama step-nya langsung')
                continue
            else:
                unknown(sentence, "tidak cocok dengan LABEL atau nama step manapun di "
                                   "step library -- cek ejaan, atau step ini belum ada")
                continue

            key, base = hit
            entry = dict(base)
            entry["name"] = rename_to or key
            if custom_desc:
                entry["description"] = custom_desc
            if not _resolve_table(entry, sentence, table, unknown):
                continue
            out.append({k: v for k, v in entry.items() if v is not None})
        return out

    return type(f"Lean{base_cls.__name__}", (base_cls,), {
        "__init__": __init__,
        "label":    label,
        "read_json": read_json,
        "entries":  entries,
    })


def _read_json_safe(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def scan_lean_sources(config_dir: str, base_cls, steps_json_path: str,
                       ota_only: bool = False) -> list:
    """Scan <config_dir>/*.feature dan cocokkan tiap satu dengan JSON
    sebelahnya (nama sama) kalau ada:

      - Tidak ada JSON sama sekali            -> lean murni (semua dari
        .feature + step library). Cuma dipakai kalau ota_only=False --
        suite OTA SELALU butuh JSON kecil utk fw_version (lihat di bawah).
      - Ada JSON tapi TIDAK punya "steps"/"tests" (cuma pengaturan lain,
        mis. "fw_version"/"_dialog") -> lean juga, tapi read_json() baca
        JSON kecil itu supaya field pengaturannya (yang dibaca base_cls,
        mis. TM81OtaTestSource.make_item() lewat self._cfg) tetap jalan.
        Daftar/urutan step TETAP dari .feature, bukan dari JSON ini.
      - Ada JSON DAN punya "steps"/"tests"     -> itu suite JSON penuh,
        dilewati di sini (ditangani wrap_if_feature_exists / jalur biasa).

    ota_only membedakan dua base_cls yang mungkin dipanggil untuk folder
    config TM81 yang SAMA (TM81GenericTestSource vs TM81OtaTestSource):
    JSON pengaturan kecil dengan field "fw_version" di root HANYA diproses
    kalau ota_only=True, JSON pengaturan tanpa "fw_version" (atau tanpa
    JSON sama sekali) HANYA diproses kalau ota_only=False -- jadi satu
    .feature tidak pernah dobel-diproses oleh dua base_cls berbeda.
    """
    sources = []
    try:
        cls_cache = {}
        for fname in sorted(os.listdir(config_dir)):
            if not fname.endswith(".feature"):
                continue
            stem = fname[:-len(".feature")]
            json_sibling = os.path.join(config_dir, f"{stem}.json")
            settings_json_path = None

            if os.path.isfile(json_sibling):
                data = _read_json_safe(json_sibling)
                if data is None or data.get("steps") or data.get("tests"):
                    continue  # gagal baca / suite JSON penuh -> jalur biasa
                is_ota_settings = "fw_version" in data
                if is_ota_settings != ota_only:
                    continue  # bukan jatah base_cls ini -- biar yg lain proses
                settings_json_path = json_sibling
            elif ota_only:
                continue  # OTA selalu butuh JSON kecil (fw_version) -- lihat docstring

            path = os.path.join(config_dir, fname)
            key = settings_json_path or "__none__"
            try:
                if key not in cls_cache:
                    cls_cache[key] = make_lean_source_class(
                        base_cls, steps_json_path, settings_json_path)
                sources.append(cls_cache[key](path))
            except Exception as e:
                _log.warning("Gagal load lean suite %s: %s", fname, e)
    except OSError:
        pass
    return sources
