"""
lib/validation_rules.py — Strategy objects untuk validasi field sebelum test dijalankan,
                          plus apply_expect_check() untuk validasi response GET command.

Setiap 'rule' di tm81_test.json (mis. {"device_id": 1}, {"dev_addr": "nonzero_hex"})
diterjemahkan jadi objek ValidationRule lewat build_rule(). test_loader.py cukup
panggil rule.check(value) — tidak perlu tahu jenis rule-nya sama sekali.

Menambah jenis rule baru = menambah 1 class baru + satu baris di build_rule(),
tanpa mengubah loop validasi di test_loader.py (Open/Closed Principle).

apply_expect_check(result, expect):
  Dipakai loader setelah execute() untuk bandingkan field OK: response vs expect dict.
  Nilai di expect bisa literal ("Deactivated") atau referensi commissioning.json
  dengan prefix @: "@user_set_config.activation".
"""

import json as _json
import os as _os


class ValidationRule:
    """Interface rule validasi. Semua rule konkret meng-override kedua method ini."""

    def check(self, value: str) -> bool:
        raise NotImplementedError

    def default_message(self, param: str) -> str:
        raise NotImplementedError


class MinLengthRule(ValidationRule):
    """Rule numerik di JSON (mis. 16) -> panjang string minimal segitu."""

    def __init__(self, n: int):
        self.n = n

    def check(self, value: str) -> bool:
        return len(value) >= self.n

    def default_message(self, param: str) -> str:
        return f"{param} belum diisi (butuh {self.n} karakter). Buka Commissioning Settings."


class NonzeroHexRule(ValidationRule):
    """Rule string "nonzero_hex" di JSON -> nilai hex tidak boleh 0."""

    def check(self, value: str) -> bool:
        try:
            return value != "" and int(value, 16) != 0
        except ValueError:
            return False

    def default_message(self, param: str) -> str:
        return f"{param} tidak boleh 0. Buka Commissioning Settings."


class NonzeroRule(ValidationRule):
    """Rule string "nonzero" di JSON -> nilai integer tidak boleh 0.
    Dipakai untuk field dropdown seperti counter_res dan submit_id
    di mana nilai 0 berarti pilihan terendah yang tidak valid di produksi."""

    def check(self, value: str) -> bool:
        try:
            return value != "" and int(value) != 0
        except (ValueError, TypeError):
            return False

    def default_message(self, param: str) -> str:
        return f"{param} tidak valid (nilai 0 tidak diperbolehkan). Buka Commissioning Settings."


# Pesan custom per-parameter, override default_message() rule di atas.
# Tambah field baru yang butuh pesan khusus cukup nambah satu baris di sini —
# tidak perlu nambah cabang if di dalam logika validasi.
CUSTOM_MESSAGES = {
    "device_id": "device_id kosong — isi field 'Device ID / Serial No.' di UI",
}


def build_rule(raw) -> ValidationRule:
    """Factory: ubah nilai rule mentah dari JSON jadi objek ValidationRule."""
    if isinstance(raw, int):
        return MinLengthRule(raw)
    if raw == "nonzero_hex":
        return NonzeroHexRule()
    if raw == "nonzero":
        return NonzeroRule()
    raise ValueError(f"Jenis validasi tidak dikenal: {raw!r}")


def validation_message(param: str, rule: ValidationRule) -> str:
    """Pesan NG yang ditampilkan ke operator — custom kalau ada, default kalau tidak."""
    return CUSTOM_MESSAGES.get(param, rule.default_message(param))


# ---------------------------------------------------------------------------
# apply_expect_check — validasi response GET command vs expect dict di JSON
# ---------------------------------------------------------------------------

_COMM_JSON = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)),
    "..", "commands", "tm81", "config", "commissioning.json"
)

# Mapping commissioning field → display value (sama dengan yang ada di command class)
_COMMISSIONING_DISPLAY: dict = {
    "user_set_config.activation":  {0: "Deactivated", 1: "Activated"},
    "user_set_config.submit_id":   {0: "15min", 1: "30min", 2: "1h", 3: "3h",
                                    4: "12h",  5: "1day", 6: "3day", 7: "7day"},
    "user_set_config.counter_res": {0: "1L", 1: "10L", 2: "100L"},
    "user_set_config.msg_type":    {0: "Unconfirmed", 1: "Confirmed"},
}


def _resolve_commissioning_ref(ref: str) -> "str | None":
    """Resolve 'section.field' dari commissioning.json → display string.
    Return None jika file tidak ada atau field tidak ditemukan (skip check).
    """
    try:
        with open(_COMM_JSON, encoding="utf-8") as f:
            comm = _json.load(f)
    except Exception:
        return None
    section, _, field = ref.partition(".")
    raw = comm.get(section, {}).get(field)
    if raw is None:
        return None
    map_key = f"{section}.{field}"
    if map_key in _COMMISSIONING_DISPLAY:
        return _COMMISSIONING_DISPLAY[map_key].get(raw, str(raw))
    if field == "timezone":
        t = int(raw)
        return f"GMT{'+' if t >= 0 else ''}{t}"
    return str(raw)


def apply_expect_check(result: str, expect: dict) -> str:
    """Bandingkan key-value field di response 'OK:...' dengan expect dict.

    Nilai di expect:
      - String literal  : "Deactivated"
      - Ref commissioning: "@user_set_config.activation"  (resolved + display-mapped)

    Return: result asli jika semua cocok, "NG:..." jika ada mismatch.
    Jika result bukan OK: langsung return tanpa cek (sudah gagal).
    """
    if not expect or not result:
        return result
    s = str(result)
    if not s.upper().startswith("OK:"):
        return result

    # Parse "Key: Value" dari tiap baris response
    parsed: dict = {}
    for line in s[3:].split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip()] = v.strip()

    for key, expected in expect.items():
        if isinstance(expected, str) and expected.startswith("@"):
            resolved = _resolve_commissioning_ref(expected[1:])
            if resolved is None:
                continue          # field tidak ada di commissioning, skip
            expected = resolved

        actual = parsed.get(key)
        if actual is None:
            return f"NG:Field '{key}' tidak ada di response"
        if str(actual).lower() != str(expected).lower():
            return f"NG:{key}: diharapkan '{expected}', dapat '{actual}'"

    return result
